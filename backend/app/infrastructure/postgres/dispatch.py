"""Short-transaction outbox leases with per-run event ordering."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.domain.events import DomainEvent
from app.infrastructure.postgres.models import EventRecord, OutboxRecord
from app.ports.dispatch import DispatchItem


class PostgresDispatchQueue:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, lease_seconds: float = 15,
    ) -> None:
        self.sessions = sessions
        self.lease_seconds = lease_seconds

    async def claim(self, limit: int) -> tuple[DispatchItem, ...]:
        now = datetime.now(timezone.utc)
        older_outbox, older_event = aliased(OutboxRecord), aliased(EventRecord)
        # An older unpublished event blocks later same-run events even when
        # its next retry is in the future. Other runs can still progress.
        earlier_unpublished = exists(select(older_outbox.outbox_id).join(
            older_event, older_outbox.event_id == older_event.event_id,
        ).where(
            older_outbox.run_id == OutboxRecord.run_id,
            older_outbox.published_at.is_(None), older_event.seq < EventRecord.seq,
        ))
        claimed: list[DispatchItem] = []
        async with self.sessions.begin() as session:
            rows = (await session.execute(
                select(OutboxRecord, EventRecord).join(
                    EventRecord, EventRecord.event_id == OutboxRecord.event_id,
                ).where(
                    OutboxRecord.published_at.is_(None),
                    OutboxRecord.next_attempt_at <= now, ~earlier_unpublished,
                ).order_by(OutboxRecord.run_id, EventRecord.seq).limit(limit)
                .with_for_update(of=OutboxRecord, skip_locked=True),
            )).all()
            for outbox, record in rows:
                outbox.attempts += 1
                # next_attempt_at doubles as a lease; crash recovery requires
                # no extra status or migration. Redis I/O occurs after commit.
                outbox.next_attempt_at = now + timedelta(seconds=self.lease_seconds)
                claimed.append(DispatchItem(
                    outbox.outbox_id, outbox.attempts,
                    DomainEvent.model_validate(record, from_attributes=True),
                ))
        return tuple(claimed)

    async def sent(self, outbox_id: str) -> None:
        async with self.sessions.begin() as session:
            await session.execute(update(OutboxRecord).where(
                OutboxRecord.outbox_id == outbox_id, OutboxRecord.published_at.is_(None),
            ).values(published_at=datetime.now(timezone.utc)))

    async def retry(self, outbox_id: str, delay_seconds: float) -> None:
        async with self.sessions.begin() as session:
            await session.execute(update(OutboxRecord).where(
                OutboxRecord.outbox_id == outbox_id, OutboxRecord.published_at.is_(None),
            ).values(next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)))
