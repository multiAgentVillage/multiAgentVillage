"""Durable dispatch queue contracts; Redis and SQLAlchemy stay in adapters."""
from dataclasses import dataclass
from typing import Protocol

from app.domain.events import DomainEvent


@dataclass(frozen=True)
class DispatchItem:
    outbox_id: str
    attempts: int
    event: DomainEvent


class DispatchQueue(Protocol):
    async def claim(self, limit: int) -> tuple[DispatchItem, ...]: ...
    async def sent(self, outbox_id: str) -> None: ...
    async def retry(self, outbox_id: str, delay_seconds: float) -> None: ...
