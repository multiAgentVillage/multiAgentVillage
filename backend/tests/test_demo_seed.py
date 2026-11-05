"""Insert-only initialization and read pagination against an isolated migrated DB."""
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.infrastructure.postgres.demo import initialize_demo
from app.infrastructure.postgres.models import AgentState, Base, LocationState, Run
from app.infrastructure.postgres.workbench import PostgresWorkbenchQueries

if os.getenv("RUN_POSTGRES_TESTS") != "1":
    pytest.skip("requires explicit RUN_POSTGRES_TESTS=1 and an independent test DB", allow_module_level=True)


@pytest_asyncio.fixture
async def seeded():
    url = Settings().sqlalchemy_url
    if not url.database or "test" not in url.database.lower():
        pytest.fail("demo tests require an independent test database")
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    run_id = f"demo-test-{uuid4().hex}"
    try:
        yield sessions, run_id
    finally:
        async with sessions.begin() as session:
            for table in reversed(Base.metadata.sorted_tables):
                if "run_id" in table.c:
                    await session.execute(delete(table).where(table.c.run_id == run_id))
        await engine.dispose()


async def test_demo_has_five_locations_eight_agents_and_chen_yu_at_teaching_building(seeded):
    sessions, run_id = seeded
    assert await initialize_demo(sessions, run_id)
    view = await PostgresWorkbenchQueries(sessions).state(run_id)
    assert len(view.locations) == 5 and len(view.agents) == 8
    chen_yu = next(agent for agent in view.agents if agent.name == "陈宇")
    assert chen_yu.location_id == "teaching-building" and chen_yu.location_name == "教学楼"


async def test_repeat_initialization_preserves_existing_run_and_agent_changes(seeded):
    sessions, run_id = seeded
    await initialize_demo(sessions, run_id)
    async with sessions.begin() as session:
        await session.execute(update(Run).where(Run.run_id == run_id).values(status="PAUSED", last_seq=17))
        await session.execute(update(AgentState).where(
            AgentState.run_id == run_id, AgentState.agent_id == "chen-yu",
        ).values(location_id="library", plan_version=3))
    assert not await initialize_demo(sessions, run_id)
    async with sessions() as session:
        run = await session.get(Run, run_id)
        agent = await session.get(AgentState, (run_id, "chen-yu"))
        assert run.status == "PAUSED" and run.last_seq == 17
        assert agent.location_id == "library" and agent.plan_version == 3
        assert await session.scalar(select(func.count()).select_from(LocationState).where(LocationState.run_id == run_id)) == 5


async def test_concurrent_initialization_has_one_winner_and_no_partial_state(seeded):
    import asyncio
    sessions, run_id = seeded
    results = await asyncio.gather(initialize_demo(sessions, run_id), initialize_demo(sessions, run_id))
    assert sorted(results) == [False, True]
    view = await PostgresWorkbenchQueries(sessions).state(run_id)
    assert len(view.agents) == 8 and len(view.locations) == 5 and view.last_seq == 0
