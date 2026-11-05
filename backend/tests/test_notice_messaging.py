"""Walking skeleton delivery, retry and observation tests.

Pure transport tests use a faithful small Redis double. PostgreSQL tests opt in
with RUN_POSTGRES_TESTS=1 and a migrated DB whose name contains test. Their
sessions share an outer transaction which is always rolled back.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.exceptions import ResponseError
from redis.asyncio import Redis
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.outbox_dispatcher import OutboxDispatcher
from app.cognition.observers import CognitionObserver
from app.config import Settings
from app.domain.events import DomainEvent, EventType
from app.infrastructure.postgres.dispatch import PostgresDispatchQueue
from app.infrastructure.postgres.models import (
    AgentState, ConsumerReceipt, EventRecord, Experiment, Memory, OutboxRecord, Run,
)
from app.infrastructure.postgres.observations import PostgresObservationStore
from app.infrastructure.realtime import ConnectionManager, RealtimeObserver
from app.infrastructure.redis.transport import EventHub, RedisStreamTransport, reconcile_once
from app.ports.dispatch import DispatchItem


def notice(**changes) -> DomainEvent:
    return DomainEvent.model_validate({
        "event_id": "evt-notice", "run_id": "run-notice", "seq": 1,
        "type": "NoticePublished", "schema_version": 1, "sim_time_ms": 0,
        "occurred_at": "2026-11-05T00:00:00Z", "correlation_id": "cmd-notice",
        "causation_id": "cmd-notice",
        "payload": {"content": "读书会今天下午举行", "recipient_agent_ids": [f"agent-{i}" for i in range(8)]},
        **changes,
    })


class RecordingObserver:
    observer_id = "recording"

    def __init__(self, fail_once=False):
        self.events = []
        self.fail_once = fail_once

    async def on_event(self, event):
        if self.fail_once:
            self.fail_once = False
            raise ConnectionError("temporary observation failure")
        self.events.append(event)


class FakeRedis:
    """Tracks independent group offsets and reclaimable unacknowledged entries."""
    def __init__(self):
        self.messages = []
        self.groups = {}

    async def xadd(self, stream, fields):
        item = (f"{len(self.messages) + 1}-0", fields)
        self.messages.append(item)
        return item[0]

    async def xgroup_create(self, stream, group, **kwargs):
        if group in self.groups:
            raise ResponseError("BUSYGROUP")
        self.groups[group] = {"offset": 0, "pending": {}}

    async def xautoclaim(self, stream, group, consumer, **kwargs):
        return ["0-0", list(self.groups[group]["pending"].values()), []]

    async def xreadgroup(self, group, consumer, streams, **kwargs):
        state = self.groups[group]
        messages = self.messages[state["offset"]:]
        state["offset"] = len(self.messages)
        state["pending"].update(dict((item[0], item) for item in messages))
        return [(next(iter(streams)), messages)] if messages else []

    async def xack(self, stream, group, message_id):
        return self.groups[group]["pending"].pop(message_id, None) is not None


@pytest.mark.asyncio
async def test_two_groups_receive_independent_copies_and_subject_unsubscribes():
    redis = FakeRedis()
    transport = RedisStreamTransport(redis)
    display, cognition = RecordingObserver(), RecordingObserver()
    display_hub, cognition_hub = EventHub(), EventHub()
    display_hub.subscribe(EventType.NOTICE_PUBLISHED, display)
    cognition_hub.subscribe(EventType.NOTICE_PUBLISHED, cognition)
    event = notice()
    await transport.publish(event)
    assert json.loads(redis.messages[0][1]["event"])["payload"]["content"] == event.payload["content"]
    assert await transport.consume_once("display", "api-1", display_hub) == 1
    assert await transport.consume_once("cognition", "cog-1", cognition_hub) == 1
    assert display.events == cognition.events == [event]
    display_hub.unsubscribe(EventType.NOTICE_PUBLISHED, display.observer_id)
    await display_hub.notify(event)
    assert len(display.events) == 1


@pytest.mark.asyncio
async def test_handler_failure_stays_pending_and_is_reclaimed_after_consumer_restart():
    redis = FakeRedis()
    transport = RedisStreamTransport(redis)
    observer = RecordingObserver(fail_once=True)
    hub = EventHub()
    hub.subscribe(EventType.NOTICE_PUBLISHED, observer)
    await transport.publish(notice())
    assert await transport.consume_once("cognition", "crashed-consumer", hub) == 0
    assert len(redis.groups["cognition"]["pending"]) == 1
    assert await transport.consume_once("cognition", "replacement-consumer", hub) == 1
    assert not redis.groups["cognition"]["pending"]
    assert observer.events == [notice()]


@pytest.mark.asyncio
async def test_unexpected_redis_group_errors_are_not_ignored():
    class DeniedRedis(FakeRedis):
        async def xgroup_create(self, *args, **kwargs):
            raise ResponseError("NOAUTH")
    with pytest.raises(ResponseError, match="NOAUTH"):
        await RedisStreamTransport(DeniedRedis()).consume_once("display", "api", EventHub())


@pytest.mark.asyncio
async def test_real_redis_independent_groups_pending_reclaim_and_restart():
    if os.getenv("RUN_REDIS_TESTS") != "1":
        pytest.skip("explicit RUN_REDIS_TESTS=1 required")
    redis = Redis.from_url(Settings().redis_url.get_secret_value(), decode_responses=True)
    stream = "campus:test:notice:" + uuid4().hex
    try:
        transport = RedisStreamTransport(redis, stream_name=stream, retry_idle_ms=0)
        failing, display = RecordingObserver(fail_once=True), RecordingObserver()
        cognition_hub, display_hub = EventHub(), EventHub()
        cognition_hub.subscribe(EventType.NOTICE_PUBLISHED, failing)
        display_hub.subscribe(EventType.NOTICE_PUBLISHED, display)
        await transport.publish(notice())
        assert await transport.consume_once("cognition", "old-process", cognition_hub) == 0
        assert (await redis.xpending(stream, "cognition"))["pending"] == 1
        assert await transport.consume_once("display", "api-process", display_hub) == 1
        restarted = RedisStreamTransport(redis, stream_name=stream, retry_idle_ms=0)
        assert await restarted.consume_once("cognition", "new-process", cognition_hub) == 1
        assert (await redis.xpending(stream, "cognition"))["pending"] == 0
        assert failing.events == display.events == [notice()]
    finally:
        # Only this test's uniquely named stream is removed.
        await redis.delete(stream)
        await redis.aclose()


@pytest.mark.asyncio
async def test_publish_failure_schedules_retry_and_then_marks_success():
    event = notice()
    class Queue:
        def __init__(self):
            self.attempt = 0
            self.retries, self.completed = [], []
        async def claim(self, limit):
            self.attempt += 1
            return (DispatchItem("out-1", self.attempt, event),)
        async def retry(self, key, seconds):
            self.retries.append((key, seconds))
        async def sent(self, key):
            self.completed.append(key)
    class Publisher:
        def __init__(self):
            self.fail = True
        async def publish(self, event):
            if self.fail:
                self.fail = False
                raise ConnectionError("Redis temporarily offline")
    queue, publisher = Queue(), Publisher()
    dispatcher = OutboxDispatcher(queue, publisher)
    assert await dispatcher.dispatch_once() == 0
    assert queue.retries == [("out-1", 1)] and queue.completed == []
    assert await dispatcher.dispatch_once() == 1
    assert queue.completed == ["out-1"]


class Socket:
    def __init__(self, *, slow=False):
        self.slow = slow
        self.accepted = False
        self.closed = False
        self.messages = []
    async def accept(self):
        self.accepted = True
    async def send_json(self, message):
        if self.slow:
            await asyncio.sleep(10)
        self.messages.append(message)
    async def close(self, code):
        self.closed = True


@pytest.mark.asyncio
async def test_websocket_hint_scoping_and_slow_client_isolation():
    manager = ConnectionManager(send_timeout=0.02)
    good, slow, other = Socket(), Socket(slow=True), Socket()
    await manager.connect("run-notice", good)
    await manager.connect("run-notice", slow)
    await manager.connect("other-run", other)
    await asyncio.wait_for(manager.broadcast(notice()), timeout=1)
    assert good.messages == [{"type": "events_available", "run_id": "run-notice", "seq": 1, "event_id": "evt-notice"}]
    assert other.messages == [] and slow.closed
    manager.disconnect("run-notice", good)
    await manager.broadcast(notice())
    assert len(good.messages) == 1


@pytest_asyncio.fixture
async def pg():
    if os.getenv("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("explicit RUN_POSTGRES_TESTS=1 required")
    url = Settings().sqlalchemy_url
    if not url.database or "test" not in url.database.lower():
        pytest.fail("requires a migrated independent database with 'test' in its name")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            outer = await conn.begin()
            try:
                sessions = async_sessionmaker(conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
                suffix = uuid4().hex[:12]
                run_id, event_id = f"msg-run-{suffix}", f"msg-event-{suffix}"
                event = notice(run_id=run_id, event_id=event_id)
                await conn.execute(insert(Experiment), {"experiment_id": suffix, "name": "message test"})
                await conn.execute(insert(Run), {"run_id": run_id, "experiment_id": suffix, "status": "RUNNING", "config_snapshot": {}})
                for agent_id in event.payload["recipient_agent_ids"]:
                    await conn.execute(insert(AgentState), {"run_id": run_id, "agent_id": agent_id})
                values = event.model_dump(mode="json")
                values["occurred_at"] = event.occurred_at
                await conn.execute(insert(EventRecord), values)
                await conn.execute(insert(OutboxRecord), {"outbox_id": "out-" + suffix, "run_id": run_id, "event_id": event_id})
                yield conn, sessions, event, "out-" + suffix
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pg_duplicate_delivery_and_group_effects_are_separate(pg):
    conn, sessions, event, _ = pg
    observer = CognitionObserver(PostgresObservationStore(sessions))
    await observer.on_event(event)
    await observer.on_event(event)
    assert await conn.scalar(select(func.count()).select_from(Memory).where(Memory.source_event_id == event.event_id)) == 8
    assert await conn.scalar(select(func.count()).select_from(ConsumerReceipt).where(ConsumerReceipt.event_id == event.event_id)) == 1
    broadcaster = RecordingObserver()
    class Broadcaster:
        async def broadcast(self, event):
            await broadcaster.on_event(event)
    realtime = RealtimeObserver(sessions, Broadcaster())
    await realtime.on_event(event)
    await realtime.on_event(event)
    assert broadcaster.events == [event]
    assert await conn.scalar(select(func.count()).select_from(ConsumerReceipt).where(ConsumerReceipt.event_id == event.event_id)) == 2


@pytest.mark.asyncio
async def test_pg_failed_memory_flush_rolls_back_receipt_and_all_eight_memories(pg, monkeypatch):
    conn, sessions, event, _ = pg
    observer = CognitionObserver(PostgresObservationStore(sessions))
    original_flush = AsyncSession.flush
    async def fail_after_flush(self, *args, **kwargs):
        await original_flush(self, *args, **kwargs)
        raise ConnectionError("failure after memory inserts")
    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "flush", fail_after_flush)
        with pytest.raises(ConnectionError, match="after memory"):
            await observer.on_event(event)
    assert await conn.scalar(select(func.count()).select_from(Memory).where(Memory.source_event_id == event.event_id)) == 0
    assert await conn.scalar(select(func.count()).select_from(ConsumerReceipt).where(ConsumerReceipt.event_id == event.event_id)) == 0
    await observer.on_event(event)
    assert await conn.scalar(select(func.count()).select_from(Memory).where(Memory.source_event_id == event.event_id)) == 8


@pytest.mark.asyncio
async def test_pg_reconcile_repairs_lost_stream_history_without_duplicate_effects(pg):
    conn, sessions, event, _ = pg
    hub = EventHub()
    hub.subscribe(EventType.NOTICE_PUBLISHED, CognitionObserver(PostgresObservationStore(sessions)))
    assert await reconcile_once(sessions, "cognition", hub) >= 1
    assert await reconcile_once(sessions, "cognition", hub) == 0
    assert await conn.scalar(select(func.count()).select_from(Memory).where(Memory.source_event_id == event.event_id)) == 8


@pytest.mark.asyncio
async def test_pg_outbox_lease_failure_retry_and_ordering(pg):
    conn, sessions, event, outbox_id = pg
    next_event = notice(event_id=event.event_id + "-next", run_id=event.run_id, seq=2)
    values = next_event.model_dump(mode="json")
    values["occurred_at"] = next_event.occurred_at
    await conn.execute(insert(EventRecord), values)
    await conn.execute(insert(OutboxRecord), {"outbox_id": outbox_id + "-next", "run_id": event.run_id, "event_id": next_event.event_id})
    queue = PostgresDispatchQueue(sessions)
    claimed = await queue.claim(50)
    assert [item.event.event_id for item in claimed if item.event.run_id == event.run_id] == [event.event_id]
    assert not [item for item in await queue.claim(50) if item.event.run_id == event.run_id]
    # Simulate lease expiry after a crash before the external publish.
    await conn.execute(update(OutboxRecord).where(OutboxRecord.outbox_id == outbox_id).values(
        next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    ))
    retried = [item for item in await queue.claim(50) if item.event.run_id == event.run_id]
    assert len(retried) == 1 and retried[0].attempts == 2
    await queue.sent(outbox_id)
    later = [item for item in await queue.claim(50) if item.event.run_id == event.run_id]
    assert [item.event.seq for item in later] == [2]


@pytest.mark.asyncio
async def test_pg_display_retry_rolls_back_receipt_until_broadcast_succeeds(pg):
    conn, sessions, event, _ = pg
    class FailOnce:
        def __init__(self):
            self.fail = True
            self.sent = []
        async def broadcast(self, event):
            if self.fail:
                self.fail = False
                raise ConnectionError("temporary display failure")
            self.sent.append(event)
    broadcaster = FailOnce()
    observer = RealtimeObserver(sessions, broadcaster)
    with pytest.raises(ConnectionError, match="display failure"):
        await observer.on_event(event)
    assert await conn.scalar(select(func.count()).select_from(ConsumerReceipt).where(ConsumerReceipt.event_id == event.event_id)) == 0
    await observer.on_event(event)
    assert broadcaster.sent == [event]
