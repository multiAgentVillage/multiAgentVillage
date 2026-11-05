"""OutboxDispatcher loop, hosted in the Runtime process."""
import asyncio

from app.application.outbox_dispatcher import OutboxDispatcher
from app.bootstrap import Resources
from app.infrastructure.redis.transport import RedisStreamTransport
from app.infrastructure.postgres.dispatch import PostgresDispatchQueue
from app.workers.base import repeat


async def run(resources: Resources, stop: asyncio.Event) -> None:
    publisher = RedisStreamTransport(resources.redis, stream_name=resources.settings.event_stream)
    dispatcher = OutboxDispatcher(PostgresDispatchQueue(resources.sessions), publisher)
    await repeat("OutboxDispatcher", stop, resources.settings.worker_poll_interval_seconds, dispatcher.dispatch_once)
