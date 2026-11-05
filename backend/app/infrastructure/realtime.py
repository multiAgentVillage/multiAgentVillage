"""Best-effort WebSocket hints; PostgreSQL event queries remain authoritative."""
import asyncio
from typing import Protocol

from fastapi import WebSocket
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.events import DomainEvent
from app.infrastructure.postgres.models import ConsumerReceipt, EventRecord


class Broadcaster(Protocol):
    async def broadcast(self, event: DomainEvent) -> None: ...


class ConnectionManager:
    def __init__(self, *, send_timeout: float = 1) -> None:
        self.send_timeout = send_timeout
        self._clients: dict[str, dict[WebSocket, asyncio.Lock]] = {}

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.setdefault(run_id, {})[websocket] = asyncio.Lock()

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        clients = self._clients.get(run_id)
        if clients is not None:
            clients.pop(websocket, None)
            if not clients:
                self._clients.pop(run_id, None)

    async def broadcast(self, event: DomainEvent) -> None:
        hint = {
            "type": "events_available", "run_id": event.run_id,
            "seq": event.seq, "event_id": event.event_id,
        }
        clients = tuple(self._clients.get(event.run_id, {}).items())

        async def send(websocket: WebSocket, lock: asyncio.Lock) -> None:
            async def locked_send() -> None:
                async with lock:
                    await websocket.send_json(hint)
            try:
                await asyncio.wait_for(locked_send(), timeout=self.send_timeout)
            except Exception:
                # One disconnected/slow browser must not block the durable
                # display group. Its next REST catch-up repairs missed hints.
                self.disconnect(event.run_id, websocket)
                try:
                    await asyncio.wait_for(websocket.close(code=1013), timeout=0.2)
                except Exception:
                    pass
        await asyncio.gather(*(send(websocket, lock) for websocket, lock in clients))


class RealtimeObserver:
    observer_id = "display"

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], broadcaster: Broadcaster,
    ) -> None:
        self.sessions = sessions
        self.broadcaster = broadcaster

    async def on_event(self, event: DomainEvent) -> None:
        async with self.sessions.begin() as session:
            record = await session.get(EventRecord, event.event_id)
            if record is None or DomainEvent.model_validate(record, from_attributes=True) != event:
                raise ValueError("display notification must match a committed event")
            claimed = await session.scalar(insert(ConsumerReceipt).values(
                consumer_name="display", event_id=event.event_id, run_id=event.run_id,
            ).on_conflict_do_nothing(
                index_elements=["consumer_name", "event_id"],
            ).returning(ConsumerReceipt.event_id))
            if claimed is not None:
                # If broadcasting itself fails, receipt commit is rolled back.
                # Crashing after a send before commit may duplicate a hint.
                await self.broadcaster.broadcast(event)
