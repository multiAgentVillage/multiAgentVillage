"""Publish leased durable work without holding a world transaction."""
import logging

from app.ports.dispatch import DispatchQueue
from app.ports.repositories import EventPublisher

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    def __init__(
        self, queue: DispatchQueue, publisher: EventPublisher,
        *, retry_base_seconds: float = 1,
    ) -> None:
        self.queue = queue
        self.publisher = publisher
        self.retry_base_seconds = retry_base_seconds

    async def dispatch_once(self, limit: int = 50) -> int:
        published = 0
        for item in await self.queue.claim(limit):
            try:
                await self.publisher.publish(item.event)
            except Exception:
                await self.queue.retry(
                    item.outbox_id, min(30, self.retry_base_seconds * 2 ** min(item.attempts - 1, 5)),
                )
                logger.exception("outbox publish will retry event=%s attempt=%s", item.event.event_id, item.attempts)
                continue
            await self.queue.sent(item.outbox_id)
            published += 1
        return published
