"""Real PostgreSQL concurrency check for a coherent workbench state view.

Opt in against an already migrated, independent database whose name contains
'test'. Only the randomly named experiment and run owned by this test are removed.
"""
import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.infrastructure.postgres.models import AgentState, Base, Experiment, LocationState, Run
from app.infrastructure.postgres.workbench import PostgresWorkbenchQueries

if os.getenv("RUN_POSTGRES_TESTS") != "1":
    pytest.skip("requires explicit RUN_POSTGRES_TESTS=1 and an independent test DB", allow_module_level=True)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sandbox():
    url = Settings().sqlalchemy_url
    if not url.database or "test" not in url.database.lower():
        pytest.fail("workbench consistency tests require an independent test database")
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex
    experiment_id, run_id = f"view-test-exp-{suffix}", f"view-test-run-{suffix}"
    try:
        async with sessions() as session, session.begin():
            session.add(Experiment(experiment_id=experiment_id, name="工作台一致性测试"))
            await session.flush()
            session.add(Run(
                run_id=run_id, experiment_id=experiment_id, status="RUNNING",
                config_snapshot={"name": "工作台一致性测试", "agents": [
                    {"agent_id": "chen-yu", "name": "陈宇"},
                ]},
            ))
            await session.flush()
            session.add_all([
                LocationState(run_id=run_id, location_id="teaching-building", name="教学楼"),
                LocationState(run_id=run_id, location_id="library", name="图书馆"),
            ])
            await session.flush()
            session.add(AgentState(run_id=run_id, agent_id="chen-yu", location_id="teaching-building"))
        yield SimpleNamespace(engine=engine, sessions=sessions, run_id=run_id)
    finally:
        async with sessions() as session, session.begin():
            for table in reversed(Base.metadata.sorted_tables):
                if "run_id" in table.c:
                    await session.execute(delete(table).where(table.c.run_id == run_id))
                elif "experiment_id" in table.c:
                    await session.execute(delete(table).where(table.c.experiment_id == experiment_id))
        await engine.dispose()


async def wait_for_database_lock(sessions, backend_pid: int) -> None:
    """Observe PostgreSQL's actual lock wait rather than infer it from a sleep."""
    deadline = asyncio.get_running_loop().time() + 5
    async with sessions() as session:
        while asyncio.get_running_loop().time() < deadline:
            blockers = await session.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": backend_pid})
            if blockers:
                return
            await asyncio.sleep(0.01)
    pytest.fail("world writer did not wait for the workbench's shared run lock")


async def test_state_view_holds_shared_run_lock_until_child_rows_are_read(sandbox):
    between_queries = asyncio.Event()
    release_reader = asyncio.Event()
    writer_committed = asyncio.Event()
    writer_pid = asyncio.get_running_loop().create_future()

    class PausingReadSession(AsyncSession):
        async def scalars(self, statement, *args, **kwargs):
            # Pause the real reader after its run query but before child queries.
            entities = [item.get("entity") for item in getattr(statement, "column_descriptions", ())]
            if LocationState in entities:
                between_queries.set()
                await release_reader.wait()
            return await super().scalars(statement, *args, **kwargs)

    async def write_world():
        async with sandbox.sessions() as session, session.begin():
            writer_pid.set_result(await session.scalar(select(func.pg_backend_pid())))
            await session.scalars(select(Run).where(Run.run_id == sandbox.run_id).with_for_update())
            await session.execute(update(Run).where(Run.run_id == sandbox.run_id).values(last_seq=1))
            await session.execute(update(LocationState).where(
                LocationState.run_id == sandbox.run_id,
                LocationState.location_id == "teaching-building",
            ).values(is_open=False))
            await session.execute(update(AgentState).where(
                AgentState.run_id == sandbox.run_id, AgentState.agent_id == "chen-yu",
            ).values(location_id="library"))
        writer_committed.set()

    reads = PostgresWorkbenchQueries(async_sessionmaker(
        sandbox.engine, class_=PausingReadSession, expire_on_commit=False,
    ))
    reader_task = asyncio.create_task(reads.state(sandbox.run_id))
    writer_task = None
    try:
        await asyncio.wait_for(between_queries.wait(), timeout=5)
        writer_task = asyncio.create_task(write_world())
        backend_pid = await asyncio.wait_for(writer_pid, timeout=5)
        await wait_for_database_lock(sandbox.sessions, backend_pid)
        assert not writer_committed.is_set()

        release_reader.set()
        before = await asyncio.wait_for(reader_task, timeout=5)
        await asyncio.wait_for(writer_task, timeout=5)
        after = await PostgresWorkbenchQueries(sandbox.sessions).state(sandbox.run_id)

        assert before.last_seq == 0
        assert before.agents[0].location_id == "teaching-building"
        assert next(location for location in before.locations if location.location_id == "teaching-building").is_open
        assert after.last_seq == 1
        assert after.agents[0].location_id == "library"
        assert not next(location for location in after.locations if location.location_id == "teaching-building").is_open
    finally:
        release_reader.set()
        await asyncio.wait_for(asyncio.gather(
            *(task for task in (reader_task, writer_task) if task is not None),
            return_exceptions=True,
        ), timeout=5)
