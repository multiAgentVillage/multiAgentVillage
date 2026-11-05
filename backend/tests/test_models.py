"""Schema invariants; execution/transaction semantics need real PostgreSQL tests."""
import re
import warnings

import pytest
from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, dialect
from sqlalchemy.schema import CreateIndex, CreateTable, sort_tables_and_constraints

from app.domain.commands import CommandKind
from app.domain.decisions import ActionType
from app.domain.events import EventType
from app.domain.run_states import RunStatus
from app.infrastructure.postgres.models import Base, ModelCall


def unique_keys(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(table.primary_key.columns.keys()),
        *(tuple(c.columns.keys()) for c in table.constraints if isinstance(c, UniqueConstraint)),
    }


def test_complete_baseline_has_named_constraints_and_no_fk_cycles():
    assert set(Base.metadata.tables) == {
        "experiments", "agent_profiles", "runs", "agent_states", "location_states",
        "activities", "commands", "events", "outbox", "consumer_receipts", "memories",
        "decision_jobs", "model_calls", "snapshots",
    }
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ordered = list(sort_tables_and_constraints(Base.metadata.tables.values()))
    # Deferred FKs would require ALTER/drop ordering and complicate the baseline.
    assert not ordered[-1][1]
    names: list[str] = []
    for table in Base.metadata.tables.values():
        assert table.primary_key.columns
        for constraint in table.constraints:
            assert constraint.name, f"unnamed constraint on {table.name}"
            names.append(constraint.name)
        for index in table.indexes:
            assert index.name
            names.append(index.name)
    assert len(names) == len(set(names))


@pytest.mark.parametrize(("table_name", "key"), [
    ("commands", ("request_id",)),
    ("events", ("event_id",)),
    ("events", ("run_id", "seq")),
    ("outbox", ("event_id",)),
    ("consumer_receipts", ("consumer_name", "event_id")),
    ("decision_jobs", ("task_key",)),
    ("snapshots", ("run_id", "seq", "sim_time_ms")),
])
def test_retries_and_replay_have_database_uniqueness(table_name, key):
    assert key in unique_keys(table_name)


@pytest.mark.parametrize(("table_name", "local", "remote"), [
    ("commands", ("run_id", "result_event_id"), ("events.run_id", "events.event_id")),
    ("outbox", ("run_id", "event_id"), ("events.run_id", "events.event_id")),
    ("consumer_receipts", ("run_id", "event_id"), ("events.run_id", "events.event_id")),
    ("memories", ("run_id", "source_event_id"), ("events.run_id", "events.event_id")),
    ("memories", ("run_id", "agent_id"), ("agent_states.run_id", "agent_states.agent_id")),
    ("decision_jobs", ("run_id", "source_event_id"), ("events.run_id", "events.event_id")),
    ("decision_jobs", ("run_id", "agent_id"), ("agent_states.run_id", "agent_states.agent_id")),
    ("model_calls", ("run_id", "job_id"), ("decision_jobs.run_id", "decision_jobs.job_id")),
    ("activities", ("run_id", "location_id"), ("location_states.run_id", "location_states.location_id")),
    ("agent_states", ("run_id", "location_id"), ("location_states.run_id", "location_states.location_id")),
    ("agent_states", ("run_id", "activity_id"), ("activities.run_id", "activities.activity_id")),
])
def test_cross_run_links_are_rejected_by_composite_foreign_keys(table_name, local, remote):
    keys = {
        (tuple(fk.column_keys), tuple(element.target_fullname for element in fk.elements))
        for fk in Base.metadata.tables[table_name].foreign_key_constraints
    }
    assert (local, remote) in keys


@pytest.mark.parametrize(("table_name", "check_name", "enum_type"), [
    ("events", "ck_events_type", EventType),
    ("commands", "ck_commands_type", CommandKind),
    ("runs", "ck_runs_status", RunStatus),
    ("agent_states", "ck_agent_states_action_type", ActionType),
])
def test_database_enumerations_match_domain_contracts(table_name, check_name, enum_type):
    constraint = next(
        c for c in Base.metadata.tables[table_name].constraints
        if isinstance(c, CheckConstraint) and c.name == check_name
    )
    allowed = set(re.findall(r"'([^']+)'", str(constraint.sqltext)))
    assert allowed == {item.value for item in enum_type}


def test_postgresql_ddl_preserves_time_payload_and_opaque_ids():
    pg = dialect()
    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=pg))
        assert "CREATE TABLE" in sql
        for column in table.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone, f"{column} must preserve UTC offsets"
            if column.name.endswith("_id"):
                assert isinstance(column.type, String), f"{column} must accept opaque IDs"
        for index in table.indexes:
            assert "INDEX" in str(CreateIndex(index).compile(dialect=pg))
    for table_name, column_name in [
        ("events", "payload"), ("commands", "payload"),
        ("runs", "config_snapshot"), ("snapshots", "world_state"),
        ("decision_jobs", "input_context_versions"),
    ]:
        assert isinstance(Base.metadata.tables[table_name].c[column_name].type, JSONB)
    # No FK can express an OR between event and command causes.
    assert not Base.metadata.tables["events"].c.causation_id.foreign_keys


def test_only_unfinished_decision_jobs_are_unique_per_agent():
    index = next(i for i in Base.metadata.tables["decision_jobs"].indexes if i.unique)
    assert tuple(index.columns.keys()) == ("run_id", "agent_id")
    sql = str(CreateIndex(index).compile(dialect=dialect()))
    assert "CREATE UNIQUE INDEX" in sql
    assert "WHERE status IN ('pending','running')" in sql


def test_unknown_model_usage_stays_nullable_without_zero_defaults():
    for name in ("input_tokens", "output_tokens", "latency_ms"):
        column = ModelCall.__table__.c[name]
        assert column.nullable
        assert column.default is None
        assert column.server_default is None
