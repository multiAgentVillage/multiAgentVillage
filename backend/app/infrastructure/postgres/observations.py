"""PostgreSQL adapter: a cognition receipt and its memories share a transaction."""
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.events import DomainEvent, EventType
from app.infrastructure.postgres.models import AgentState, ConsumerReceipt, EventRecord, Memory


class PostgresObservationStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def record(self, event: DomainEvent, agent_ids: tuple[str, ...]) -> bool:
        async with self.sessions.begin() as session:
            record = await session.get(EventRecord, event.event_id)
            if record is None or DomainEvent.model_validate(record, from_attributes=True) != event:
                raise ValueError("observation must match a committed authoritative event")
            claimed = await session.scalar(
                insert(ConsumerReceipt).values(
                    consumer_name="cognition", event_id=event.event_id, run_id=event.run_id,
                ).on_conflict_do_nothing(
                    index_elements=["consumer_name", "event_id"],
                ).returning(ConsumerReceipt.event_id)
            )
            if claimed is None:
                return False
            if event.type != EventType.NOTICE_PUBLISHED:
                return True
            content = event.payload.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("notice content is required")
            actual_agents = set((await session.scalars(
                select(AgentState.agent_id).where(
                    AgentState.run_id == event.run_id, AgentState.agent_id.in_(agent_ids),
                ),
            )).all())
            if actual_agents != set(agent_ids):
                raise ValueError("notice audience contains an agent outside this run")
            for agent_id in agent_ids:
                # A second independent safeguard if this effect is later refactored.
                memory_id = "mem-" + str(uuid5(NAMESPACE_URL, f"{event.event_id}:{agent_id}"))
                session.add(Memory(
                    memory_id=memory_id, run_id=event.run_id, agent_id=agent_id,
                    source_event_id=event.event_id, sim_time_ms=event.sim_time_ms,
                    content=content, importance=1, topics=["notice"],
                ))
            await session.flush()
            return True
