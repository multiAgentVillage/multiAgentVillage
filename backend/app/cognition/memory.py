"""Observation application service; storage implements receipt atomicity."""
from app.domain.decisions import DecisionContext
from app.domain.events import DomainEvent
from app.ports.observations import ObservationStore


class MemoryService:
    def __init__(self, store: ObservationStore) -> None:
        self.store = store

    async def record(self, event: DomainEvent, agent_ids: tuple[str, ...]) -> bool:
        return await self.store.record(event, agent_ids)

    async def retrieve(self, context: DecisionContext) -> tuple[str, ...]:
        raise NotImplementedError("Decision-time memory retrieval belongs to a later stage")
