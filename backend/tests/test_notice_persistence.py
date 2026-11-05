"""Real transaction tests for the stage-three notice vertical slice.

Opt in with RUN_POSTGRES_TESTS=1 against a migrated, independent database whose
name contains 'test'. Each test creates random owned rows and deletes only those
rows, because adapters intentionally commit their production transactions.
"""
import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.command_processor import CommandProcessor, ProcessStatus
from app.application.simulation_facade import SimulationFacade
from app.config import Settings
from app.domain.commands import CommandEnvelope, CommandStatus
from app.infrastructure.postgres.models import (
    AgentState, Base, CommandRecord, EventRecord, Experiment, OutboxRecord, Run,
)
from app.infrastructure.postgres.repositories import (
    PostgresCommandInbox, PostgresOutboxStore, PostgresReadService,
    PostgresUnitOfWork, PublishNoticeCodec, RequestConflict, RunNotFound,
)

if os.getenv("RUN_POSTGRES_TESTS") != "1":
    pytest.skip("requires explicit RUN_POSTGRES_TESTS=1 and an independent test DB", allow_module_level=True)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sandbox():
    url = Settings().sqlalchemy_url
    if not url.database or "test" not in url.database.lower():
        pytest.fail("notice transaction tests require an independent test database")
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex
    experiment_id, run_id = f"notice-test-exp-{suffix}", f"notice-test-run-{suffix}"
    other_run = f"notice-test-other-{suffix}"
    agent_ids = tuple(f"notice-test-agent-{index}" for index in range(8))
    try:
        async with sessions() as session, session.begin():
            session.add(Experiment(experiment_id=experiment_id, name="通知事务测试"))
            await session.flush()
            session.add_all([
                Run(run_id=run_id, experiment_id=experiment_id, status="RUNNING", config_snapshot={}),
                Run(run_id=other_run, experiment_id=experiment_id, status="RUNNING", config_snapshot={}),
            ])
            await session.flush()
            session.add_all([AgentState(run_id=run_id, agent_id=agent_id) for agent_id in agent_ids])
        yield SimpleNamespace(
            sessions=sessions, run_id=run_id, other_run=other_run, agent_ids=agent_ids,
            processor=CommandProcessor(lambda: PostgresUnitOfWork(sessions), PublishNoticeCodec()),
            inbox=PostgresCommandInbox(sessions), reads=PostgresReadService(sessions),
        )
    finally:
        # FK dependency order, with every deletion scoped to this test's IDs.
        async with sessions() as session, session.begin():
            for table in reversed(Base.metadata.sorted_tables):
                if "run_id" in table.c:
                    await session.execute(delete(table).where(table.c.run_id.in_((run_id, other_run))))
                elif "experiment_id" in table.c:
                    await session.execute(delete(table).where(table.c.experiment_id == experiment_id))
        await engine.dispose()


def notice(sandbox, *, request_id: str | None = None, content: str = "今晚活动通知", **changes):
    return CommandEnvelope.model_validate({
        "command_id": f"cmd-{uuid4()}", "request_id": request_id or f"req-{uuid4()}",
        "run_id": sandbox.run_id, "type": "PublishNotice",
        "payload": {"content": content}, **changes,
    })


async def count(sandbox, model) -> int:
    async with sandbox.sessions() as session:
        return await session.scalar(select(func.count()).select_from(model).where(model.run_id == sandbox.run_id))


async def test_receipt_is_accepted_before_runtime_and_applied_only_after_atomic_commit(sandbox):
    facade = SimulationFacade(sandbox.inbox, sandbox.reads)
    envelope = notice(sandbox)
    receipt = await facade.submit(envelope)
    assert receipt.status == CommandStatus.ACCEPTED and receipt.result_event_ids == ()
    assert await count(sandbox, EventRecord) == await count(sandbox, OutboxRecord) == 0
    result = await sandbox.processor.process_next(sandbox.run_id)
    assert result.status == ProcessStatus.APPLIED
    events = await sandbox.reads.events_after(sandbox.run_id, 0, limit=100)
    assert len(events) == 1 and events[0].causation_id == envelope.command_id
    assert events[0].seq == 1 and events[0].payload["recipient_agent_ids"] == sandbox.agent_ids
    receipt = await sandbox.inbox.append(envelope.model_copy(update={"command_id": f"cmd-{uuid4()}"}))
    assert receipt.command_id == envelope.command_id and receipt.status == CommandStatus.APPLIED
    assert receipt.result_event_ids == (events[0].event_id,)
    assert await count(sandbox, CommandRecord) == await count(sandbox, EventRecord) == await count(sandbox, OutboxRecord) == 1
    async with sandbox.sessions() as session:
        assert (await session.get(Run, sandbox.run_id)).last_seq == 1


async def test_concurrent_retries_share_the_original_command(sandbox):
    request_id = f"req-{uuid4()}"
    receipts = await asyncio.gather(*[
        sandbox.inbox.append(notice(sandbox, request_id=request_id)) for _ in range(4)
    ])
    assert len({receipt.command_id for receipt in receipts}) == 1
    assert all(receipt.status == CommandStatus.ACCEPTED for receipt in receipts)
    assert await count(sandbox, CommandRecord) == 1


async def test_concurrent_different_content_with_same_key_conflicts(sandbox):
    request_id = f"req-{uuid4()}"
    results = await asyncio.gather(
        sandbox.inbox.append(notice(sandbox, request_id=request_id, content="活动A")),
        sandbox.inbox.append(notice(sandbox, request_id=request_id, content="活动B")),
        return_exceptions=True,
    )
    assert sum(isinstance(result, RequestConflict) for result in results) == 1
    assert sum(not isinstance(result, BaseException) for result in results) == 1
    assert await count(sandbox, CommandRecord) == 1


async def test_request_key_includes_run_and_version_not_new_command_id(sandbox):
    original = notice(sandbox)
    await sandbox.inbox.append(original)
    for change in ({"run_id": sandbox.other_run}, {"schema_version": 2}, {"type": "PauseRun"}):
        with pytest.raises(RequestConflict):
            await sandbox.inbox.append(CommandEnvelope.model_validate({
                **original.model_dump(), "command_id": f"cmd-{uuid4()}", **change,
            }))
    assert await count(sandbox, CommandRecord) == 1


async def test_failed_outbox_write_rolls_back_seq_event_and_command_then_retries(sandbox, monkeypatch):
    envelope = notice(sandbox)
    await sandbox.inbox.append(envelope)
    original_add = PostgresOutboxStore.add

    async def fail_after_outbox_insert(self, events):
        await original_add(self, events)
        raise RuntimeError("injected storage interruption")

    monkeypatch.setattr(PostgresOutboxStore, "add", fail_after_outbox_insert)
    with pytest.raises(RuntimeError, match="injected storage interruption"):
        await sandbox.processor.process_next(sandbox.run_id)
    async with sandbox.sessions() as session:
        assert (await session.get(Run, sandbox.run_id)).last_seq == 0
        assert (await session.get(CommandRecord, envelope.command_id)).status == "pending"
    assert await count(sandbox, EventRecord) == await count(sandbox, OutboxRecord) == 0
    monkeypatch.setattr(PostgresOutboxStore, "add", original_add)
    assert (await sandbox.processor.process_next(sandbox.run_id)).status == ProcessStatus.APPLIED
    assert await count(sandbox, EventRecord) == await count(sandbox, OutboxRecord) == 1


async def test_concurrent_runtime_invocations_allocate_one_ordered_sequence(sandbox):
    await sandbox.inbox.append(notice(sandbox, content="第一条通知"))
    await sandbox.inbox.append(notice(sandbox, content="第二条通知"))
    results = await asyncio.gather(
        sandbox.processor.process_next(sandbox.run_id), sandbox.processor.process_next(sandbox.run_id),
    )
    assert all(result.status == ProcessStatus.APPLIED for result in results)
    events = await sandbox.reads.events_after(sandbox.run_id, 0, limit=100)
    assert [event.seq for event in events] == [1, 2]
    assert (await sandbox.processor.process_next(sandbox.run_id)).status == ProcessStatus.IDLE


async def test_incremental_query_has_exclusive_cursor_and_page_limit(sandbox):
    for index in range(3):
        await sandbox.inbox.append(notice(sandbox, content=f"通知{index}"))
        await sandbox.processor.process_next(sandbox.run_id)
    first = await sandbox.reads.events_after(sandbox.run_id, 0, limit=2)
    second = await sandbox.reads.events_after(sandbox.run_id, first[-1].seq, limit=2)
    assert [event.seq for event in first + second] == [1, 2, 3]
    assert await sandbox.reads.events_after(sandbox.run_id, second[-1].seq, limit=2) == ()
    assert [event.seq for event in await sandbox.reads.between(sandbox.run_id, 1, 2)] == [2]


@pytest.mark.parametrize("changes", [
    {"schema_version": 2}, {"type": "CloseLocation"}, {"payload": {}},
    {"payload": {"content": " "}}, {"payload": {"content": "通知", "recipient_agent_ids": ["unknown"]}},
    {"payload": {"content": "通知", "command_id": "forged-cause"}},
])
async def test_invalid_command_is_durably_rejected_without_notice_event(sandbox, changes):
    envelope = notice(sandbox, **changes)
    await sandbox.inbox.append(envelope)
    result = await sandbox.processor.process_next(sandbox.run_id)
    assert result.status == ProcessStatus.REJECTED
    receipt = await sandbox.inbox.append(envelope)
    assert receipt.status == CommandStatus.REJECTED and receipt.reason
    assert await count(sandbox, EventRecord) == await count(sandbox, OutboxRecord) == 0
    assert (await sandbox.processor.process_next(sandbox.run_id)).status == ProcessStatus.IDLE


async def test_paused_notice_is_finally_rejected_and_does_not_apply_after_resume(sandbox):
    envelope = notice(sandbox)
    await sandbox.inbox.append(envelope)
    async with sandbox.sessions() as session, session.begin():
        await session.execute(update(Run).where(Run.run_id == sandbox.run_id).values(status="PAUSED"))
    assert (await sandbox.processor.process_next(sandbox.run_id)).status == ProcessStatus.REJECTED
    receipt = await sandbox.inbox.append(envelope)
    assert receipt.status == CommandStatus.REJECTED and "PAUSED" in receipt.reason
    assert receipt.result_event_ids == ()
    assert await count(sandbox, EventRecord) == await count(sandbox, OutboxRecord) == 0
    # Test setup only; this does not expose lifecycle control in the application.
    async with sandbox.sessions() as session, session.begin():
        await session.execute(update(Run).where(Run.run_id == sandbox.run_id).values(status="RUNNING"))
    assert (await sandbox.processor.process_next(sandbox.run_id)).status == ProcessStatus.IDLE
    assert (await sandbox.inbox.append(envelope)).status == CommandStatus.REJECTED
    assert await count(sandbox, EventRecord) == await count(sandbox, OutboxRecord) == 0
    async with sandbox.sessions() as session:
        assert (await session.get(Run, sandbox.run_id)).last_seq == 0


async def test_terminal_run_rejects_notice(sandbox):
    envelope = notice(sandbox)
    await sandbox.inbox.append(envelope)
    async with sandbox.sessions() as session, session.begin():
        await session.execute(update(Run).where(Run.run_id == sandbox.run_id).values(status="FINISHED"))
    assert (await sandbox.processor.process_next(sandbox.run_id)).status == ProcessStatus.REJECTED
    assert await count(sandbox, EventRecord) == 0


async def test_missing_run_does_not_create_command(sandbox):
    with pytest.raises(RunNotFound):
        await sandbox.inbox.append(notice(sandbox, run_id=f"missing-{uuid4()}"))
    assert await count(sandbox, CommandRecord) == 0
