"""PostgreSQL records for plan 2.1, section 3.9.

These records describe storage only. World changes, budget reservations and
consumer effects still belong in their application-level UnitOfWork. IDs are
opaque strings, so identifiers such as ``run-001`` remain valid.
"""
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKeyConstraint,
    Index, Integer, MetaData, PrimaryKeyConstraint, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    })


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )


class Experiment(Timestamps, Base):
    __tablename__ = "experiments"

    experiment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )


class AgentProfile(Timestamps, Base):
    __tablename__ = "agent_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["experiment_id"], ["experiments.experiment_id"],
            name="fk_agent_profiles_experiment",
        ),
        Index("ix_agent_profiles_experiment", "experiment_id"),
    )

    agent_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    biography: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    interests: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False,
    )
    goals: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False,
    )
    schedule: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False,
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )


class Run(Timestamps, Base):
    __tablename__ = "runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["experiment_id"], ["experiments.experiment_id"],
            name="fk_runs_experiment",
        ),
        CheckConstraint(
            "status IN ('DRAFT','READY','RUNNING','PAUSED','FINISHED','FAILED')",
            name="ck_runs_status",
        ),
        CheckConstraint("sim_time_ms >= 0 AND run_epoch >= 0 AND last_seq >= 0", name="ck_runs_versions"),
        CheckConstraint(
            "max_model_requests >= 0 AND max_input_tokens_per_call >= 0 "
            "AND max_output_tokens_per_call >= 0 "
            "AND model_requests_used >= 0 AND model_requests_reserved >= 0",
            name="ck_runs_budget_nonnegative",
        ),
        Index("ix_runs_experiment", "experiment_id"),
    )

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="DRAFT", nullable=False)
    sim_time_ms: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)
    run_epoch: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    last_seq: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)
    # The application copies editable templates once and treats this as immutable.
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Initial suggestions from section 3.7; adjustable limits, no pricing algorithm.
    max_model_requests: Mapped[int] = mapped_column(Integer, server_default="120", nullable=False)
    max_input_tokens_per_call: Mapped[int] = mapped_column(Integer, server_default="2000", nullable=False)
    max_output_tokens_per_call: Mapped[int] = mapped_column(Integer, server_default="300", nullable=False)
    model_requests_used: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    model_requests_reserved: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    recovery_reason: Mapped[str | None] = mapped_column(Text)


class LocationState(Base):
    __tablename__ = "location_states"
    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["runs.run_id"], name="fk_location_states_run"),
        CheckConstraint("resource_version >= 0", name="ck_location_states_version"),
        CheckConstraint("capacity IS NULL OR capacity >= 0", name="ck_location_states_capacity"),
    )

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    location_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer)
    resource_version: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["runs.run_id"], name="fk_activities_run"),
        ForeignKeyConstraint(
            ["run_id", "location_id"],
            ["location_states.run_id", "location_states.location_id"],
            name="fk_activities_location_in_run",
        ),
        CheckConstraint("starts_at_ms >= 0 AND ends_at_ms >= starts_at_ms", name="ck_activities_schedule"),
        CheckConstraint("resource_version >= 0", name="ck_activities_version"),
        CheckConstraint("status IN ('scheduled','active','finished','cancelled')", name="ck_activities_status"),
        Index("ix_activities_run_schedule", "run_id", "starts_at_ms"),
    )

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    activity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    location_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_at_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ends_at_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="scheduled", nullable=False)
    resource_version: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    # Participation is a compact run-local record for the eight-agent MVP.
    participants: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False,
    )
    state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )


class AgentState(Base):
    __tablename__ = "agent_states"
    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["runs.run_id"], name="fk_agent_states_run"),
        ForeignKeyConstraint(
            ["run_id", "location_id"],
            ["location_states.run_id", "location_states.location_id"],
            name="fk_agent_states_location_in_run",
        ),
        ForeignKeyConstraint(
            ["run_id", "activity_id"], ["activities.run_id", "activities.activity_id"],
            name="fk_agent_states_activity_in_run",
        ),
        CheckConstraint("plan_version >= 0", name="ck_agent_states_plan_version"),
        CheckConstraint(
            "action_type IS NULL OR action_type IN ('MOVE','TALK','WAIT','JOIN_ACTIVITY')",
            name="ck_agent_states_action_type",
        ),
        CheckConstraint(
            "(action_started_at_ms IS NULL OR action_started_at_ms >= 0) "
            "AND (action_ends_at_ms IS NULL OR action_ends_at_ms >= 0) "
            "AND (action_started_at_ms IS NULL OR action_ends_at_ms IS NULL "
            "OR action_ends_at_ms >= action_started_at_ms)",
            name="ck_agent_states_action_time",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # No FK to mutable profiles: run-local identity comes from config_snapshot.
    location_id: Mapped[str | None] = mapped_column(String(128))
    activity_id: Mapped[str | None] = mapped_column(String(128))
    plan_version: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    plan: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )
    position: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )
    action_id: Mapped[str | None] = mapped_column(String(128))
    action_type: Mapped[str | None] = mapped_column(String(32))
    # Persist origin/destination/path and other action parameters for interpolation.
    action_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )
    action_started_at_ms: Mapped[int | None] = mapped_column(BigInteger)
    action_ends_at_ms: Mapped[int | None] = mapped_column(BigInteger)
    state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )


# String + CHECK keeps the baseline inspectable and avoids PostgreSQL ENUM
# lifecycle changes when an event is added. Tests keep these equal to contracts.
EVENT_TYPES = (
    "RunStarted", "RunPaused", "RunResumed", "RunStopped", "NoticePublished",
    "LocationClosed", "ActivityTimeChanged", "AgentObserved", "DecisionRequested",
    "DecisionRecorded", "ActionStarted", "AgentArrived", "MessageDelivered",
    "ActionInterrupted", "ActionRejected",
)
COMMAND_TYPES = (
    "ValidateConfig", "StartRun", "PauseRun", "ResumeRun", "StopRun",
    "PublishNotice", "CloseLocation", "ChangeActivityTime", "ProposeAction",
    "CompleteAction",
)


def _allowed_values(column: str, values: tuple[str, ...]) -> str:
    """Build CHECK SQL only from the static internal enum values above."""
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["runs.run_id"], name="fk_events_run"),
        UniqueConstraint("run_id", "seq", name="uq_events_run_seq"),
        # Composite references prove memories/jobs/outbox belong to the same run.
        UniqueConstraint("run_id", "event_id", name="uq_events_run_event"),
        CheckConstraint(_allowed_values("type", EVENT_TYPES), name="ck_events_type"),
        CheckConstraint("seq > 0 AND schema_version > 0 AND sim_time_ms >= 0", name="ck_events_versions"),
        Index("ix_events_run_sim_time", "run_id", "sim_time_ms", "seq"),
        Index("ix_events_correlation", "correlation_id"),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    sim_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # A cause can be a command OR an event; it intentionally has no single FK.
    causation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class CommandRecord(Base):
    __tablename__ = "commands"
    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["runs.run_id"], name="fk_commands_run"),
        ForeignKeyConstraint(
            ["run_id", "result_event_id"], ["events.run_id", "events.event_id"],
            name="fk_commands_result_event_in_run",
        ),
        UniqueConstraint("request_id", name="uq_commands_request_id"),
        CheckConstraint(_allowed_values("type", COMMAND_TYPES), name="ck_commands_type"),
        CheckConstraint("schema_version > 0", name="ck_commands_schema_version"),
        CheckConstraint("status IN ('pending','applied','rejected')", name="ck_commands_status"),
        Index("ix_commands_run_pending", "run_id", "status", "received_at", "command_id"),
    )

    command_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), server_default="pending", nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    causation_id: Mapped[str | None] = mapped_column(String(128))
    result_event_id: Mapped[str | None] = mapped_column(String(128))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxRecord(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "event_id"], ["events.run_id", "events.event_id"],
            name="fk_outbox_event_in_run",
        ),
        UniqueConstraint("event_id", name="uq_outbox_event_id"),
        CheckConstraint("attempts >= 0", name="ck_outbox_attempts"),
        Index(
            "ix_outbox_unpublished", "next_attempt_at", "run_id",
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    outbox_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class ConsumerReceipt(Base):
    __tablename__ = "consumer_receipts"
    __table_args__ = (
        PrimaryKeyConstraint("consumer_name", "event_id", name="pk_consumer_receipts"),
        ForeignKeyConstraint(
            ["run_id", "event_id"], ["events.run_id", "events.event_id"],
            name="fk_consumer_receipts_event_in_run",
        ),
        Index("ix_consumer_receipts_run", "run_id"),
    )

    # This composite PK is also the required consumer/event uniqueness guarantee.
    consumer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "agent_id"], ["agent_states.run_id", "agent_states.agent_id"],
            name="fk_memories_agent_in_run",
        ),
        ForeignKeyConstraint(
            ["run_id", "source_event_id"], ["events.run_id", "events.event_id"],
            name="fk_memories_source_event_in_run",
        ),
        CheckConstraint("sim_time_ms >= 0 AND importance >= 0", name="ck_memories_values"),
        Index("ix_memories_agent_time", "run_id", "agent_id", "sim_time_ms"),
        Index("ix_memories_source_event", "run_id", "source_event_id"),
    )

    memory_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sim_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    topics: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class DecisionJob(Timestamps, Base):
    __tablename__ = "decision_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "agent_id"], ["agent_states.run_id", "agent_states.agent_id"],
            name="fk_decision_jobs_agent_in_run",
        ),
        ForeignKeyConstraint(
            ["run_id", "source_event_id"], ["events.run_id", "events.event_id"],
            name="fk_decision_jobs_source_event_in_run",
        ),
        UniqueConstraint("task_key", name="uq_decision_jobs_task_key"),
        UniqueConstraint("run_id", "job_id", name="uq_decision_jobs_run_job"),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','cancelled')",
            name="ck_decision_jobs_status",
        ),
        CheckConstraint(
            "run_epoch >= 0 AND agent_plan_version >= 0 AND context_event_seq >= 0 AND attempts >= 0",
            name="ck_decision_jobs_versions_attempts",
        ),
        Index("ix_decision_jobs_pending", "status", "next_attempt_at"),
        # Section 3.7: coalesce additional stimuli while one job is unfinished.
        Index(
            "uq_decision_jobs_unfinished_agent", "run_id", "agent_id", unique=True,
            postgresql_where=text("status IN ('pending','running')"),
        ),
    )

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_key: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="pending", nullable=False)
    run_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    context_event_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Version map includes the relevant locations/activities, not one world version.
    input_context_versions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )
    input_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False,
    )
    needs_reevaluation: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    claimed_by: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(128))


class ModelCall(Base):
    __tablename__ = "model_calls"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "job_id"], ["decision_jobs.run_id", "decision_jobs.job_id"],
            name="fk_model_calls_job_in_run",
        ),
        CheckConstraint("source IN ('model','rule')", name="ck_model_calls_source"),
        CheckConstraint(
            "request_status IN ('pending','running','succeeded','failed','timed_out','cancelled')",
            name="ck_model_calls_request_status",
        ),
        CheckConstraint(
            "attempt >= 1 AND (latency_ms IS NULL OR latency_ms >= 0) "
            "AND (input_tokens IS NULL OR input_tokens >= 0) "
            "AND (output_tokens IS NULL OR output_tokens >= 0)",
            name="ck_model_calls_metrics",
        ),
        Index("ix_model_calls_run_started", "run_id", "started_at"),
        Index("ix_model_calls_job", "run_id", "job_id"),
    )

    call_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(128))
    model_name: Mapped[str | None] = mapped_column(String(200))
    model_version: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    request_status: Mapped[str] = mapped_column(String(20), server_default="pending", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(BigInteger)
    # Unknown provider usage remains NULL, never a fabricated zero.
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(128))


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        ForeignKeyConstraint(["run_id"], ["runs.run_id"], name="fk_snapshots_run"),
        # Time may advance without an event, so the same seq can have later time.
        UniqueConstraint("run_id", "seq", "sim_time_ms", name="uq_snapshots_run_cursor"),
        CheckConstraint("seq >= 0 AND sim_time_ms >= 0 AND schema_version > 0", name="ck_snapshots_versions"),
        Index("ix_snapshots_run_sim_time", "run_id", "sim_time_ms"),
    )

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sim_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    world_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    canonical_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
