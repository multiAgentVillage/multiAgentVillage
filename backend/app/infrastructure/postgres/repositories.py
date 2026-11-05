"""PostgreSQL adapters for the stage-three Command/UnitOfWork ports.

Only CommandInbox opens its own short submission transaction. Repositories
owned by PostgresUnitOfWork share one AsyncSession and never commit themselves.
"""
from datetime import datetime, timezone
import hashlib
import json
from types import TracebackType
from typing import Self
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.campus_world import CampusWorld
from app.domain.commands import (
    CommandEnvelope, CommandKind, CommandReceipt, CommandStatus,
    PublishNoticeCommand, WorldCommand,
)
from app.domain.errors import CommandDecodeError
from app.domain.events import DomainEvent, EventDraft
from app.domain.memento import WorldMemento
from app.domain.run_states import RunStatus
from app.domain.world import World
from app.infrastructure.postgres.models import (
    AgentState, CommandRecord, EventRecord, LocationState, OutboxRecord, Run,
)


class RequestConflict(ValueError):
    """The same request_id was already submitted with a different intent."""


class RunNotFound(LookupError):
    """The requested run does not exist."""


def event_from_record(record: EventRecord) -> DomainEvent:
    return DomainEvent(
        event_id=record.event_id, run_id=record.run_id, seq=record.seq,
        type=record.type, schema_version=record.schema_version,
        sim_time_ms=record.sim_time_ms, occurred_at=record.occurred_at,
        correlation_id=record.correlation_id, causation_id=record.causation_id,
        payload=record.payload,
    )


def _envelope_from_record(record: CommandRecord) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=record.command_id, request_id=record.request_id,
        run_id=record.run_id, type=record.type,
        schema_version=record.schema_version, payload=record.payload,
    )


def _receipt_from_record(record: CommandRecord) -> CommandReceipt:
    return CommandReceipt(
        command_id=record.command_id,
        status=CommandStatus.ACCEPTED if record.status == "pending" else CommandStatus(record.status),
        result_event_ids=(record.result_event_id,) if record.result_event_id else (),
        reason=record.rejection_reason,
    )


def _canonical_intent(run_id: str, kind: str, version: int, payload: dict) -> str:
    return json.dumps(
        [run_id, kind, version, payload], ensure_ascii=False,
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    )


class PostgresCommandInbox:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def append(self, envelope: CommandEnvelope) -> CommandReceipt:
        # Match the frozen schema's identifier bound before issuing SQL.
        if any(len(value) > 128 for value in (
            envelope.command_id, envelope.request_id, envelope.run_id,
        )):
            raise ValueError("Identifiers must not exceed 128 characters")
        payload = envelope.payload.to_dict()
        intent = _canonical_intent(envelope.run_id, envelope.type.value, envelope.schema_version, payload)
        async with self.sessions() as session, session.begin():
            existing = (await session.scalars(select(CommandRecord).where(
                CommandRecord.request_id == envelope.request_id,
            ))).one_or_none()
            if existing is not None:
                stored_intent = _canonical_intent(existing.run_id, existing.type, existing.schema_version, existing.payload)
                if stored_intent != intent:
                    raise RequestConflict("相同请求标识已用于不同内容，请使用新的请求标识")
                return _receipt_from_record(existing)
            # The foreign key remains the final guarantee; this read gives the
            # caller an explicit 404 rather than an opaque integrity failure.
            if await session.get(Run, envelope.run_id) is None:
                raise RunNotFound(envelope.run_id)
            await session.execute(insert(CommandRecord).values(
                command_id=envelope.command_id, request_id=envelope.request_id,
                run_id=envelope.run_id, type=envelope.type.value,
                schema_version=envelope.schema_version, payload=payload,
                correlation_id=envelope.command_id,
            ).on_conflict_do_nothing(index_elements=[CommandRecord.request_id]))
            # At READ COMMITTED this statement observes a concurrent winner once
            # INSERT's unique-key wait has completed. No pre-read race exists.
            record = (await session.scalars(select(CommandRecord).where(
                CommandRecord.request_id == envelope.request_id,
            ))).one()
            stored_intent = _canonical_intent(record.run_id, record.type, record.schema_version, record.payload)
            if stored_intent != intent:
                raise RequestConflict("相同请求标识已用于不同内容，请使用新的请求标识")
            return _receipt_from_record(record)


class PublishNoticeCodec:
    """GoF Command decoder with a fixed (type, version) whitelist."""

    def decode(self, envelope: CommandEnvelope) -> WorldCommand:
        if envelope.type != CommandKind.PUBLISH_NOTICE or envelope.schema_version != 1:
            raise CommandDecodeError("本阶段仅支持PublishNotice schema_version=1")
        payload = envelope.payload.to_dict()
        if set(payload) - {"content", "recipient_agent_ids"}:
            raise CommandDecodeError("PublishNotice payload包含未知字段")
        try:
            return PublishNoticeCommand.model_validate({
                "command_id": envelope.command_id,
                "run_id": envelope.run_id, **payload,
            })
        except ValidationError as error:
            raise CommandDecodeError("PublishNotice payload格式不正确") from error


class PostgresWorldRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.loaded: dict[str, tuple[Run, CampusWorld]] = {}

    async def load(self, run_id: str, *, for_update: bool) -> CampusWorld:
        statement = select(Run).where(Run.run_id == run_id)
        if for_update:
            statement = statement.with_for_update()
        record = (await self.session.scalars(statement)).one_or_none()
        if record is None:
            raise RunNotFound(run_id)
        agent_ids = tuple((await self.session.scalars(select(AgentState.agent_id).where(
            AgentState.run_id == run_id,
        ).order_by(AgentState.agent_id))).all())
        world = CampusWorld(
            run_id=run_id, status=RunStatus(record.status),
            sim_time_ms=record.sim_time_ms, run_epoch=record.run_epoch,
            last_seq=record.last_seq, agent_ids=agent_ids,
        )
        self.loaded[run_id] = (record, world)
        return world

    async def save(self, world: World) -> None:
        if not isinstance(world, CampusWorld) or world.run_id not in self.loaded:
            raise ValueError("Only a world loaded by this UnitOfWork can be saved")
        record, _ = self.loaded[world.run_id]
        record.status = world.status.value
        record.sim_time_ms = world.sim_time_ms
        record.run_epoch = world.run_epoch
        # EventStore owns seq allocation after this save; never replace it here.
        await self.session.flush()


class PostgresCommandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_eligible(self, run_id: str, *, control_first: bool) -> CommandEnvelope | None:
        # Lifecycle controls are intentionally unsupported by this slice. The
        # invoker still locks the owning run before selecting pending commands.
        record = (await self.session.scalars(select(CommandRecord).where(
            CommandRecord.run_id == run_id, CommandRecord.status == "pending",
        ).order_by(CommandRecord.received_at, CommandRecord.command_id).limit(1).with_for_update())).one_or_none()
        return _envelope_from_record(record) if record else None

    async def defer(self, command_id: str) -> None:
        # Reserved for future deferrable actions; notices in PAUSED are rejected.
        # A deferred process result must never become a database command status.
        return None

    async def finish(self, receipt: CommandReceipt) -> None:
        if receipt.status not in (CommandStatus.APPLIED, CommandStatus.REJECTED):
            raise ValueError("Only final command results may be persisted")
        record = await self.session.get(CommandRecord, receipt.command_id)
        if record is None:
            raise LookupError(receipt.command_id)
        record.status = receipt.status.value
        record.result_event_id = receipt.result_event_ids[0] if receipt.result_event_ids else None
        record.rejection_reason = receipt.reason
        record.processed_at = datetime.now(timezone.utc)
        await self.session.flush()


class PostgresEventStore:
    def __init__(self, session: AsyncSession, worlds: PostgresWorldRepository | None = None) -> None:
        self.session = session
        self.worlds = worlds

    async def append_with_seq(self, run_id: str, drafts: tuple[EventDraft, ...]) -> tuple[DomainEvent, ...]:
        if self.worlds is None or run_id not in self.worlds.loaded:
            raise RuntimeError("Event append requires the owning run lock in a UnitOfWork")
        record, world = self.worlds.loaded[run_id]
        events = []
        for draft in drafts:
            if draft.run_id != run_id:
                raise ValueError("Event draft belongs to another run")
            record.last_seq += 1
            event = DomainEvent(
                **draft.model_dump(), event_id=f"evt-{uuid4()}", seq=record.last_seq,
            )
            values = event.model_dump()
            values["type"] = event.type.value
            self.session.add(EventRecord(**values))
            events.append(event)
        world.last_seq = record.last_seq
        await self.session.flush()
        return tuple(events)

    async def between(self, run_id: str, from_seq: int, to_seq: int) -> tuple[DomainEvent, ...]:
        records = (await self.session.scalars(select(EventRecord).where(
            EventRecord.run_id == run_id, EventRecord.seq > from_seq, EventRecord.seq <= to_seq,
        ).order_by(EventRecord.seq))).all()
        return tuple(event_from_record(record) for record in records)

    async def after(self, run_id: str, after_seq: int, *, limit: int) -> tuple[DomainEvent, ...]:
        records = (await self.session.scalars(select(EventRecord).where(
            EventRecord.run_id == run_id, EventRecord.seq > after_seq,
        ).order_by(EventRecord.seq).limit(limit))).all()
        return tuple(event_from_record(record) for record in records)


class PostgresOutboxStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, events: tuple[DomainEvent, ...]) -> None:
        self.session.add_all([OutboxRecord(
            outbox_id=f"out-{uuid4()}", run_id=event.run_id, event_id=event.event_id,
        ) for event in events])
        await self.session.flush()


class PostgresUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def __aenter__(self) -> Self:
        self.session = self.sessions()
        await self.session.begin()
        self.worlds = PostgresWorldRepository(self.session)
        self.commands = PostgresCommandRepository(self.session)
        self.events = PostgresEventStore(self.session, self.worlds)
        self.outbox = PostgresOutboxStore(self.session)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        try:
            # commit() is explicit. Exceptions and uncommitted exits roll back.
            await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class PostgresReadService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def events_after(self, run_id: str, after_seq: int, *, limit: int) -> tuple[DomainEvent, ...]:
        async with self.sessions() as session:
            if await session.get(Run, run_id) is None:
                raise RunNotFound(run_id)
            return await PostgresEventStore(session).after(run_id, after_seq, limit=limit)

    async def between(self, run_id: str, from_seq: int, to_seq: int) -> tuple[DomainEvent, ...]:
        async with self.sessions() as session:
            return await PostgresEventStore(session).between(run_id, from_seq, to_seq)

    async def current_state(self, run_id: str) -> WorldMemento:
        # A consistent read view for the Facade, not a persisted history snapshot.
        async with self.sessions() as session, session.begin():
            run = (await session.scalars(select(Run).where(
                Run.run_id == run_id,
            ).with_for_update(read=True))).one_or_none()
            if run is None:
                raise RunNotFound(run_id)
            agents = (await session.scalars(select(AgentState).where(
                AgentState.run_id == run_id,
            ).order_by(AgentState.agent_id))).all()
            locations = (await session.scalars(select(LocationState).where(
                LocationState.run_id == run_id,
            ).order_by(LocationState.location_id))).all()
            state = {
                "run_id": run.run_id, "status": run.status, "run_epoch": run.run_epoch,
                "agents": [{"agent_id": agent.agent_id, "location_id": agent.location_id,
                            "plan_version": agent.plan_version} for agent in agents],
                "locations": [{"location_id": location.location_id, "name": location.name,
                               "is_open": location.is_open} for location in locations],
            }
            encoded = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return WorldMemento(
                run_id=run_id, seq=run.last_seq, sim_time_ms=run.sim_time_ms,
                schema_version=1, state_hash=hashlib.sha256(encoded.encode()).hexdigest(),
                _opaque_state_json=encoded,
            )
