"""Independent group loops and PostgreSQL reconciliation after stream loss."""
import asyncio
import socket
from uuid import uuid4

from app.bootstrap import Resources
from app.cognition.observers import CognitionObserver
from app.domain.events import EventType
from app.infrastructure.postgres.observations import PostgresObservationStore
from app.infrastructure.realtime import ConnectionManager, RealtimeObserver
from app.infrastructure.redis.transport import EventHub, RedisStreamTransport, reconcile_once
from app.workers.base import repeat


async def run_group(resources: Resources, stop: asyncio.Event, group: str, hub: EventHub) -> None:
    transport = RedisStreamTransport(
        resources.redis, stream_name=resources.settings.event_stream,
        retry_idle_ms=resources.settings.consumer_retry_idle_ms,
    )
    consumer = f"{group}-{socket.gethostname()}-{uuid4().hex[:8]}"
    async with asyncio.TaskGroup() as tasks:
        tasks.create_task(repeat(
            f"{group} stream", stop, resources.settings.worker_poll_interval_seconds,
            lambda: transport.consume_once(group, consumer, hub),
        ))
        tasks.create_task(repeat(
            f"{group} reconciliation", stop, resources.settings.consumer_reconcile_interval_seconds,
            lambda: reconcile_once(resources.sessions, group, hub),
        ))


async def run_display(resources: Resources, connections: ConnectionManager, stop: asyncio.Event) -> None:
    hub = EventHub()
    hub.subscribe(EventType.NOTICE_PUBLISHED, RealtimeObserver(resources.sessions, connections))
    await run_group(resources, stop, "display", hub)


async def run_cognition(resources: Resources, stop: asyncio.Event) -> None:
    hub = EventHub()
    hub.subscribe(EventType.NOTICE_PUBLISHED, CognitionObserver(PostgresObservationStore(resources.sessions)))
    await run_group(resources, stop, "cognition", hub)
