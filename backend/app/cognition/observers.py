"""GoF Observer: event perception and memory storage, without world mutation."""
from typing import Protocol

from app.domain.events import DomainEvent
from app.cognition.memory import MemoryService
from app.cognition.perception import PerceptionService
from app.ports.observations import ObservationStore


class EventObserver(Protocol):
    @property
    def observer_id(self) -> str: ...
    async def on_event(self, event: DomainEvent) -> None: ...


class CognitionObserver:
    observer_id = "cognition"

    def __init__(self, store: ObservationStore) -> None:
        self.perception = PerceptionService()
        self.memories = MemoryService(store)

    async def on_event(self, event: DomainEvent) -> None:
        await self.memories.record(event, self.perception.visible_agents(event))
