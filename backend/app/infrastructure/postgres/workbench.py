"""Bounded PostgreSQL read queries; never use editable profiles for run history."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.workbench import (
    AgentDetail, AgentView, EventPage, LocationView, MemoryView, RunSummary, RunView,
)
from app.domain.commands import CommandReceipt, CommandStatus
from app.infrastructure.postgres.models import AgentState, CommandRecord, EventRecord, LocationState, Memory, Run
from app.infrastructure.postgres.repositories import RunNotFound, event_from_record


class ResourceNotFound(LookupError):
    pass


def summary(run: Run) -> RunSummary:
    return RunSummary(
        run_id=run.run_id, name=run.config_snapshot.get("name", run.run_id),
        status=run.status, sim_time_ms=run.sim_time_ms, last_seq=run.last_seq,
    )


def command_receipt(record: CommandRecord) -> CommandReceipt:
    return CommandReceipt(
        command_id=record.command_id,
        status=CommandStatus.ACCEPTED if record.status == "pending" else CommandStatus(record.status),
        result_event_ids=(record.result_event_id,) if record.result_event_id else (),
        reason=record.rejection_reason,
    )


class PostgresWorkbenchQueries:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def _run(self, session: AsyncSession, run_id: str) -> Run:
        run = await session.get(Run, run_id)
        if run is None:
            raise RunNotFound(run_id)
        return run

    async def list_runs(self) -> tuple[RunSummary, ...]:
        async with self.sessions() as session:
            runs = (await session.scalars(select(Run).order_by(Run.created_at.desc(), Run.run_id).limit(100))).all()
            return tuple(summary(run) for run in runs)

    async def state(self, run_id: str) -> RunView:
        # World writers lock this run before changing any of its child rows.
        # Hold a shared run lock until all parts of the read view are loaded.
        async with self.sessions() as session, session.begin():
            run = (await session.scalars(select(Run).where(
                Run.run_id == run_id,
            ).with_for_update(read=True))).one_or_none()
            if run is None:
                raise RunNotFound(run_id)
            locations = (await session.scalars(select(LocationState).where(
                LocationState.run_id == run_id,
            ).order_by(LocationState.location_id))).all()
            agents = (await session.scalars(select(AgentState).where(
                AgentState.run_id == run_id,
            ).order_by(AgentState.agent_id))).all()
            location_names = {location.location_id: location.name for location in locations}
            names = {agent["agent_id"]: agent["name"] for agent in run.config_snapshot.get("agents", [])}
            return RunView(
                **summary(run).model_dump(),
                locations=tuple(LocationView(location_id=row.location_id, name=row.name, is_open=row.is_open) for row in locations),
                agents=tuple(AgentView(
                    agent_id=row.agent_id, name=names.get(row.agent_id, row.agent_id),
                    location_id=row.location_id, location_name=location_names.get(row.location_id),
                ) for row in agents),
            )

    async def events(self, run_id: str, after_seq: int, limit: int) -> EventPage:
        async with self.sessions() as session:
            await self._run(session, run_id)
            records = (await session.scalars(select(EventRecord).where(
                EventRecord.run_id == run_id, EventRecord.seq > after_seq,
            ).order_by(EventRecord.seq).limit(limit + 1))).all()
            items = tuple(event_from_record(row) for row in records[:limit])
            return EventPage(items=items, next_seq=items[-1].seq if items else after_seq, has_more=len(records) > limit)

    async def receipt(self, run_id: str, command_id: str) -> CommandReceipt:
        async with self.sessions() as session:
            await self._run(session, run_id)
            record = await session.get(CommandRecord, command_id)
            if record is None or record.run_id != run_id:
                raise ResourceNotFound("command")
            return command_receipt(record)

    async def agent(self, run_id: str, agent_id: str) -> AgentDetail:
        async with self.sessions() as session:
            run = await self._run(session, run_id)
            state = await session.get(AgentState, (run_id, agent_id))
            if state is None:
                raise ResourceNotFound("agent")
            location = await session.get(LocationState, (run_id, state.location_id)) if state.location_id else None
            names = {agent["agent_id"]: agent["name"] for agent in run.config_snapshot.get("agents", [])}
            memories = (await session.scalars(select(Memory).where(
                Memory.run_id == run_id, Memory.agent_id == agent_id,
            ).join(EventRecord, EventRecord.event_id == Memory.source_event_id).order_by(
                EventRecord.seq.desc(), Memory.memory_id,
            ).limit(100))).all()
            return AgentDetail(
                agent_id=agent_id, name=names.get(agent_id, agent_id),
                location_id=state.location_id, location_name=location.name if location else None,
                memories=tuple(MemoryView(
                    memory_id=row.memory_id, source_event_id=row.source_event_id,
                    content=row.content, sim_time_ms=row.sim_time_ms,
                ) for row in memories),
            )
