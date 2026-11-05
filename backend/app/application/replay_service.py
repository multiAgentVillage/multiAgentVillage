"""Memento caretaker placeholder; history replay is not implemented yet."""
from app.domain.memento import ReadOnlyView
from app.domain.world import World
from app.ports.repositories import EventStore, SnapshotStore


class ReplayService:
    def __init__(self, snapshots: SnapshotStore, events: EventStore, world_type: type[World]) -> None:
        self.snapshots = snapshots
        self.events = events
        self.world_type = world_type

    async def state_at(self, run_id: str, seq: int) -> ReadOnlyView:
        raise NotImplementedError("ReplayService is not implemented in phase one")
