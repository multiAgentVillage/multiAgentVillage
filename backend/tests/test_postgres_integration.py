"""Real migrated PostgreSQL only; every test rolls back its own transaction.

Run explicitly with RUN_POSTGRES_TESTS=1 and DATABASE_URL pointing to a separate
database whose name contains ``test``. Apply Alembic before running this module.
The suite never creates/drops schemas, runs migrations, or cleans existing data.
"""
import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.infrastructure.postgres.models import (
    Activity, AgentProfile, AgentState, Base, CommandRecord, ConsumerReceipt,
    DecisionJob, EventRecord, Experiment, LocationState, Memory, ModelCall,
    OutboxRecord, Run, Snapshot,
)

if os.getenv("RUN_POSTGRES_TESTS") != "1":
    pytest.skip("requires explicit RUN_POSTGRES_TESTS=1 and an independent test DB", allow_module_level=True)

pytestmark = pytest.mark.asyncio

RUN_A, RUN_B = "it-run-a", "it-run-b"
EVENT_A, EVENT_B = "it-event-a", "it-event-b"
AGENT, ROOM = "it-agent", "it-room"
AT = datetime(2026, 11, 5, 10, 30, tzinfo=timezone(timedelta(hours=8)))


@pytest_asyncio.fixture
async def connection() -> AsyncIterator[AsyncConnection]:
    url = Settings().sqlalchemy_url
    if not url.database or "test" not in url.database.lower():
        pytest.fail("integration tests require a separate database with 'test' in its name")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                yield conn
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def event_values(event_id: str, run_id: str, seq: int = 1) -> dict:
    return dict(
        event_id=event_id, run_id=run_id, seq=seq, type="RunStarted",
        schema_version=1, sim_time_ms=0, occurred_at=AT,
        correlation_id="it-trace", causation_id="it-command-source",
        payload={"notice": "活动开始", "nested": {"visible": True, "agents": [AGENT]}},
    )


def command_values(command_id: str, request_id: str, **overrides) -> dict:
    return {
        "command_id": command_id, "request_id": request_id, "run_id": RUN_A,
        "type": "PauseRun", "payload": {}, "correlation_id": "it-trace", **overrides,
    }


def job_values(job_id: str, task_key: str, *, status: str = "pending") -> dict:
    return dict(
        job_id=job_id, task_key=task_key, run_id=RUN_A, agent_id=AGENT,
        source_event_id=EVENT_A, status=status, run_epoch=0, agent_plan_version=0,
        context_event_seq=1, input_context_versions={"locations": {ROOM: 0}},
        input_context={"visible_facts": ["活动开始"], "memory_refs": []},
    )


async def seed_world(conn: AsyncConnection) -> None:
    """Minimal valid parents, including two independent runs at the same seq."""
    await conn.execute(insert(Experiment), dict(
        experiment_id="it-experiment", name="集成测试", config={"seed": 7},
    ))
    await conn.execute(insert(AgentProfile), dict(
        agent_id=AGENT, experiment_id="it-experiment", name="小林",
        interests=["阅读"], goals=["参加活动"], schedule=[{"at_ms": 0}],
    ))
    for run_id in (RUN_A, RUN_B):
        await conn.execute(insert(Run), dict(
            run_id=run_id, experiment_id="it-experiment", status="RUNNING", last_seq=1,
            config_snapshot={"agents": [{"agent_id": AGENT}], "seed": 7},
        ))
        await conn.execute(insert(LocationState), dict(
            run_id=run_id, location_id=ROOM, name="活动室", capacity=8,
        ))
    await conn.execute(insert(Activity), dict(
        run_id=RUN_A, activity_id="it-activity", location_id=ROOM,
        name="读书会", starts_at_ms=0, ends_at_ms=60000, participants=[AGENT],
    ))
    for run_id in (RUN_A, RUN_B):
        await conn.execute(insert(AgentState), dict(
            run_id=run_id, agent_id=AGENT, location_id=ROOM,
        ))
    await conn.execute(insert(EventRecord), event_values(EVENT_A, RUN_A))
    await conn.execute(insert(EventRecord), event_values(EVENT_B, RUN_B))


async def reject_constraint(conn: AsyncConnection, name: str, statement, values: dict) -> None:
    """A savepoint contains the expected error so the outer fixture stays usable."""
    with pytest.raises(IntegrityError) as error:
        async with conn.begin_nested():
            await conn.execute(statement, values)
    # SQLAlchemy's asyncpg adapter chains the original PostgreSQL exception.
    cause = error.value.orig
    actual = None
    while cause is not None:
        actual = getattr(cause, "constraint_name", None)
        if actual:
            break
        cause = cause.__cause__
    assert actual == name, f"expected {name}, got {actual}"


async def test_all_fourteen_tables_roundtrip_json_time_defaults_and_unknown_usage(connection):
    await seed_world(connection)
    await connection.execute(insert(CommandRecord), command_values(
        "it-command", "it-request", status="applied", result_event_id=EVENT_A,
    ))
    await connection.execute(insert(OutboxRecord), dict(
        outbox_id="it-outbox", run_id=RUN_A, event_id=EVENT_A,
    ))
    await connection.execute(insert(ConsumerReceipt), dict(
        consumer_name="cognition", run_id=RUN_A, event_id=EVENT_A,
    ))
    await connection.execute(insert(Memory), dict(
        memory_id="it-memory", run_id=RUN_A, agent_id=AGENT,
        source_event_id=EVENT_A, sim_time_ms=0, content="活动开始了", topics=["活动"],
    ))
    await connection.execute(insert(DecisionJob), job_values("it-job", "it-task"))
    await connection.execute(insert(ModelCall), dict(
        call_id="it-call", run_id=RUN_A, job_id="it-job", source="model",
        provider="fake", model_name="fake-v1", model_version="1", prompt_version="1",
        request_status="failed", error_code="provider_usage_unknown",
    ))
    await connection.execute(insert(Snapshot), dict(
        snapshot_id="it-snapshot", run_id=RUN_A, seq=1, sim_time_ms=0,
        world_state={"agents": {AGENT: {"location_id": ROOM}}}, canonical_hash="a" * 64,
    ))
    for table in Base.metadata.sorted_tables:
        assert await connection.scalar(select(func.count()).select_from(table)) > 0, table.name
    event = (await connection.execute(select(EventRecord.__table__).where(
        EventRecord.event_id == EVENT_A,
    ))).mappings().one()
    assert event["payload"]["nested"] == {"visible": True, "agents": [AGENT]}
    assert event["occurred_at"].utcoffset() is not None
    assert event["occurred_at"] == AT.astimezone(timezone.utc)
    run = (await connection.execute(select(Run.__table__).where(Run.run_id == RUN_A))).mappings().one()
    assert (run["max_model_requests"], run["max_input_tokens_per_call"], run["max_output_tokens_per_call"]) == (120, 2000, 300)
    assert run["model_requests_reserved"] == run["model_requests_used"] == 0
    call = (await connection.execute(select(ModelCall.__table__))).mappings().one()
    assert call["input_tokens"] is call["output_tokens"] is call["latency_ms"] is None


async def test_event_sequence_is_unique_within_a_run_and_reusable_in_another(connection):
    await seed_world(connection)
    await reject_constraint(connection, "uq_events_run_seq", insert(EventRecord),
                            event_values("it-duplicate-seq", RUN_A))
    assert await connection.scalar(select(func.count()).select_from(EventRecord).where(EventRecord.seq == 1)) == 2


async def test_event_id_is_globally_unique(connection):
    await seed_world(connection)
    await reject_constraint(connection, "pk_events", insert(EventRecord), event_values(EVENT_A, RUN_B, seq=2))


async def test_request_id_deduplicates_distinct_command_ids(connection):
    await seed_world(connection)
    await connection.execute(insert(CommandRecord), command_values("it-command-a", "it-request"))
    await reject_constraint(connection, "uq_commands_request_id", insert(CommandRecord),
                            command_values("it-command-b", "it-request"))


async def test_outbox_has_one_record_per_event(connection):
    await seed_world(connection)
    await connection.execute(insert(OutboxRecord), dict(outbox_id="it-outbox-a", run_id=RUN_A, event_id=EVENT_A))
    await reject_constraint(connection, "uq_outbox_event_id", insert(OutboxRecord),
                            dict(outbox_id="it-outbox-b", run_id=RUN_A, event_id=EVENT_A))


async def test_receipts_deduplicate_one_group_and_allow_independent_groups(connection):
    await seed_world(connection)
    receipt = dict(consumer_name="cognition", run_id=RUN_A, event_id=EVENT_A)
    await connection.execute(insert(ConsumerReceipt), receipt)
    await reject_constraint(connection, "pk_consumer_receipts", insert(ConsumerReceipt), receipt)
    await connection.execute(insert(ConsumerReceipt), {**receipt, "consumer_name": "display"})
    assert await connection.scalar(select(func.count()).select_from(ConsumerReceipt)) == 2


async def test_task_key_deduplicates_even_finished_decision_jobs(connection):
    await seed_world(connection)
    await connection.execute(insert(DecisionJob), job_values("it-job-a", "it-task", status="completed"))
    await reject_constraint(connection, "uq_decision_jobs_task_key", insert(DecisionJob),
                            job_values("it-job-b", "it-task", status="completed"))


async def test_only_one_unfinished_job_per_agent_but_history_is_allowed(connection):
    await seed_world(connection)
    await connection.execute(insert(DecisionJob), job_values("it-job-a", "it-task-a"))
    await reject_constraint(connection, "uq_decision_jobs_unfinished_agent", insert(DecisionJob),
                            job_values("it-job-b", "it-task-b", status="running"))
    await connection.execute(update(DecisionJob).where(DecisionJob.job_id == "it-job-a").values(status="completed"))
    await connection.execute(insert(DecisionJob), job_values("it-job-b", "it-task-b", status="running"))
    assert await connection.scalar(select(func.count()).select_from(DecisionJob)) == 2


async def test_memory_source_event_cannot_cross_run_boundary(connection):
    await seed_world(connection)
    await reject_constraint(connection, "fk_memories_source_event_in_run", insert(Memory), dict(
        memory_id="it-invalid-memory", run_id=RUN_A, agent_id=AGENT,
        source_event_id=EVENT_B, sim_time_ms=0, content="不应读取其他运行的信息",
    ))


async def test_decision_source_event_cannot_cross_run_boundary(connection):
    await seed_world(connection)
    values = job_values("it-invalid-job", "it-invalid-task")
    values["source_event_id"] = EVENT_B
    await reject_constraint(connection, "fk_decision_jobs_source_event_in_run", insert(DecisionJob), values)


async def test_command_result_event_cannot_cross_run_boundary(connection):
    await seed_world(connection)
    await reject_constraint(connection, "fk_commands_result_event_in_run", insert(CommandRecord),
                            command_values("it-command", "it-request", result_event_id=EVENT_B))


async def test_model_call_cannot_attach_to_another_runs_job(connection):
    await seed_world(connection)
    await connection.execute(insert(DecisionJob), job_values("it-job", "it-task"))
    await reject_constraint(connection, "fk_model_calls_job_in_run", insert(ModelCall), dict(
        call_id="it-invalid-call", run_id=RUN_B, job_id="it-job", source="rule",
    ))


async def test_snapshot_cursor_is_unique_but_time_can_advance_without_events(connection):
    await seed_world(connection)
    snapshot = dict(
        snapshot_id="it-snapshot-a", run_id=RUN_A, seq=1, sim_time_ms=0,
        world_state={"agents": {}}, canonical_hash="a" * 64,
    )
    await connection.execute(insert(Snapshot), snapshot)
    await reject_constraint(connection, "uq_snapshots_run_cursor", insert(Snapshot),
                            {**snapshot, "snapshot_id": "it-snapshot-b"})
    await connection.execute(insert(Snapshot), {**snapshot, "snapshot_id": "it-snapshot-c", "sim_time_ms": 500})
    assert await connection.scalar(select(func.count()).select_from(Snapshot)) == 2


async def test_negative_budget_reservations_are_rejected(connection):
    await seed_world(connection)
    await reject_constraint(connection, "ck_runs_budget_nonnegative", insert(Run), dict(
        run_id="it-invalid-budget", experiment_id="it-experiment",
        config_snapshot={}, model_requests_reserved=-1,
    ))


async def test_failed_world_unit_of_work_leaves_no_partial_effects(connection):
    await seed_world(connection)
    with pytest.raises(RuntimeError, match="simulated unit of work failure"):
        async with connection.begin_nested():
            await connection.execute(update(Run).where(Run.run_id == RUN_A).values(last_seq=2, sim_time_ms=500))
            await connection.execute(update(AgentState).where(
                AgentState.run_id == RUN_A, AgentState.agent_id == AGENT,
            ).values(plan_version=1, position={"x": 3, "y": 4}))
            await connection.execute(insert(EventRecord), event_values("it-rollback-event", RUN_A, seq=2))
            await connection.execute(insert(OutboxRecord), dict(
                outbox_id="it-rollback-outbox", run_id=RUN_A, event_id="it-rollback-event",
            ))
            await connection.execute(insert(CommandRecord), command_values(
                "it-rollback-command", "it-rollback-request", status="applied",
                result_event_id="it-rollback-event",
            ))
            await connection.execute(insert(ConsumerReceipt), dict(
                consumer_name="it-rollback-consumer", run_id=RUN_A, event_id="it-rollback-event",
            ))
            raise RuntimeError("simulated unit of work failure")
    run = (await connection.execute(select(Run.__table__).where(Run.run_id == RUN_A))).mappings().one()
    assert run["last_seq"] == 1 and run["sim_time_ms"] == 0
    agent = (await connection.execute(select(AgentState.__table__).where(
        AgentState.run_id == RUN_A, AgentState.agent_id == AGENT,
    ))).mappings().one()
    assert agent["plan_version"] == 0 and agent["position"] == {}
    for table, predicate in [
        (EventRecord, EventRecord.event_id == "it-rollback-event"),
        (OutboxRecord, OutboxRecord.outbox_id == "it-rollback-outbox"),
        (CommandRecord, CommandRecord.command_id == "it-rollback-command"),
        (ConsumerReceipt, ConsumerReceipt.consumer_name == "it-rollback-consumer"),
    ]:
        assert await connection.scalar(select(func.count()).select_from(table).where(predicate)) == 0
    assert await connection.scalar(select(func.count()).select_from(EventRecord)) == 2
