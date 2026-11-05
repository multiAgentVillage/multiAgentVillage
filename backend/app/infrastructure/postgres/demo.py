"""Insert-only development initialization. Existing run data is never repaired/reset."""
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.demo import DEFAULT_EXPERIMENT_ID, DEFAULT_RUN_ID, default_config
from app.infrastructure.postgres.models import AgentProfile, AgentState, Experiment, LocationState, Run


async def initialize_demo(sessions: async_sessionmaker[AsyncSession], run_id: str = DEFAULT_RUN_ID) -> bool:
    """Return True only when this call created the run and all of its initial state."""
    if not run_id.strip() or len(run_id) > 128:
        raise ValueError("run_id must be a nonempty string of at most 128 characters")
    config = default_config()
    async with sessions() as session, session.begin():
        if await session.get(Run, run_id) is not None:
            return False
        await session.execute(insert(Experiment).values(
            experiment_id=DEFAULT_EXPERIMENT_ID, name=config["name"],
            description="W1通知发布闭环的开发演示模板", config=config,
        ).on_conflict_do_nothing(index_elements=["experiment_id"]))
        created = (await session.execute(insert(Run).values(
            run_id=run_id, experiment_id=DEFAULT_EXPERIMENT_ID,
            status="RUNNING", config_snapshot=config,
        ).on_conflict_do_nothing(index_elements=["run_id"]).returning(Run.run_id))).scalar_one_or_none()
        if created is None:
            return False
        for location in config["locations"]:
            session.add(LocationState(
                run_id=run_id, location_id=location["location_id"], name=location["name"],
                state={"position": location["position"]},
            ))
        # Flush parent locations before the agents' composite foreign keys.
        await session.flush()
        positions = {item["location_id"]: item["position"] for item in config["locations"]}
        for agent in config["agents"]:
            await session.execute(insert(AgentProfile).values(
                agent_id=agent["agent_id"], experiment_id=DEFAULT_EXPERIMENT_ID,
                name=agent["name"], interests=agent["interests"],
                goals=["了解社团活动"], config={"initial_location_id": agent["location_id"]},
            ).on_conflict_do_nothing(index_elements=["agent_id"]))
            session.add(AgentState(
                run_id=run_id, agent_id=agent["agent_id"], location_id=agent["location_id"],
                position=positions[agent["location_id"]],
            ))
        return True
