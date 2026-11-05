"""Redis Streams transport and the process-local GoF Observer subject."""
import logging

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cognition.observers import EventObserver
from app.domain.events import DomainEvent, EventType
from app.infrastructure.postgres.models import ConsumerReceipt, EventRecord

logger = logging.getLogger(__name__)


class EventHub:
    """Each process registers its own observers; Redis handles group broadcast."""

    def __init__(self) -> None:
        self._subscriptions: dict[EventType, dict[str, EventObserver]] = {}

    def subscribe(self, kind: EventType, observer: EventObserver) -> None:
        self._subscriptions.setdefault(kind, {})[observer.observer_id] = observer

    def unsubscribe(self, kind: EventType, observer_id: str) -> None:
        self._subscriptions.get(kind, {}).pop(observer_id, None)

    async def notify(self, event: DomainEvent) -> None:
        for observer in tuple(self._subscriptions.get(event.type, {}).values()):
            await observer.on_event(event)


class RedisStreamTransport:
    def __init__(
        self, redis: Redis, stream_name: str = "campus:events", retry_idle_ms: int = 1000,
    ) -> None:
        self.redis = redis
        self.stream_name = stream_name
        self.retry_idle_ms = retry_idle_ms
        self._claim_cursors: dict[tuple[str, str], str] = {}

    async def publish(self, event: DomainEvent) -> None:
        # Redis IDs are transport offsets, never domain seq values.
        await self.redis.xadd(self.stream_name, {"event": event.model_dump_json()})

    async def _ensure_group(self, group: str) -> None:
        try:
            await self.redis.xgroup_create(self.stream_name, group, id="0-0", mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def consume_once(self, group: str, consumer: str, hub: EventHub) -> int:
        """Reclaim idle pending messages, then read new ones; ACK after effects."""
        await self._ensure_group(group)
        key = (group, consumer)
        result = await self.redis.xautoclaim(
            self.stream_name, group, consumer, min_idle_time=self.retry_idle_ms,
            start_id=self._claim_cursors.get(key, "0-0"), count=50,
        )
        self._claim_cursors[key] = result[0]
        messages = result[1]
        if not messages:
            streams = await self.redis.xreadgroup(
                group, consumer, {self.stream_name: ">"}, count=50, block=100,
            )
            messages = [message for _, batch in streams for message in batch]
        acknowledged = 0
        for message_id, fields in messages:
            try:
                event = DomainEvent.model_validate_json(fields["event"])
                await hub.notify(event)
                await self.redis.xack(self.stream_name, group, message_id)
                acknowledged += 1
            except Exception:
                # A handler/DB failure, or a crash after commit before XACK,
                # leaves a recoverable pending delivery.
                logger.exception("event delivery remains pending group=%s message=%s", group, message_id)
        return acknowledged


async def reconcile_once(
    sessions: async_sessionmaker[AsyncSession], consumer_name: str, hub: EventHub,
    limit: int = 100,
) -> int:
    """Repair missing notice observations even when Redis lost published data.

    Run separately from stream reads: Redis failure must not block PG recovery.
    """
    async with sessions() as session:
        records = (await session.scalars(
            select(EventRecord).where(
                EventRecord.type == EventType.NOTICE_PUBLISHED.value,
                ~exists(select(ConsumerReceipt.event_id).where(
                    ConsumerReceipt.consumer_name == consumer_name,
                    ConsumerReceipt.event_id == EventRecord.event_id,
                )),
            ).order_by(EventRecord.run_id, EventRecord.seq).limit(limit),
        )).all()
        events = [DomainEvent.model_validate(record, from_attributes=True) for record in records]
    handled = 0
    for event in events:
        try:
            await hub.notify(event)
            handled += 1
        except Exception:
            logger.exception("event reconciliation failed consumer=%s event=%s", consumer_name, event.event_id)
    return handled
