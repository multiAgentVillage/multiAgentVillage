"""Atomic observation persistence port; cognition does not own a DB session."""
from typing import Protocol

from app.domain.events import DomainEvent


class ObservationStore(Protocol):
    async def record(self, event: DomainEvent, agent_ids: tuple[str, ...]) -> bool:
        """Commit the receipt and all memories, or none. False means duplicate."""
        ...
