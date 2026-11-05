"""Freeze the fourteen-table storage model from plan 2.1, section 3.9.

Revision ID: 0002_core_schema
Revises: 0001_baseline

This revision freezes its own DDL. It intentionally does not import live ORM
metadata; future model changes require a new revision.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_core_schema"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create authoritative state, durable messages and cognition history."""
    op.create_table('experiments',
    sa.Column('experiment_id', sa.String(length=128), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), server_default='', nullable=False),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('experiment_id', name=op.f('pk_experiments'))
    )
    op.create_table('agent_profiles',
    sa.Column('agent_id', sa.String(length=128), nullable=False),
    sa.Column('experiment_id', sa.String(length=128), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('biography', sa.Text(), server_default='', nullable=False),
    sa.Column('interests', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('goals', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('schedule', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['experiment_id'], ['experiments.experiment_id'], name='fk_agent_profiles_experiment'),
    sa.PrimaryKeyConstraint('agent_id', name=op.f('pk_agent_profiles'))
    )
    op.create_index('ix_agent_profiles_experiment', 'agent_profiles', ['experiment_id'], unique=False)
    op.create_table('runs',
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('experiment_id', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='DRAFT', nullable=False),
    sa.Column('sim_time_ms', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('run_epoch', sa.Integer(), server_default='0', nullable=False),
    sa.Column('last_seq', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('max_model_requests', sa.Integer(), server_default='120', nullable=False),
    sa.Column('max_input_tokens_per_call', sa.Integer(), server_default='2000', nullable=False),
    sa.Column('max_output_tokens_per_call', sa.Integer(), server_default='300', nullable=False),
    sa.Column('model_requests_used', sa.Integer(), server_default='0', nullable=False),
    sa.Column('model_requests_reserved', sa.Integer(), server_default='0', nullable=False),
    sa.Column('recovery_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('DRAFT','READY','RUNNING','PAUSED','FINISHED','FAILED')", name='ck_runs_status'),
    sa.CheckConstraint('max_model_requests >= 0 AND max_input_tokens_per_call >= 0 AND max_output_tokens_per_call >= 0 AND model_requests_used >= 0 AND model_requests_reserved >= 0', name='ck_runs_budget_nonnegative'),
    sa.CheckConstraint('sim_time_ms >= 0 AND run_epoch >= 0 AND last_seq >= 0', name='ck_runs_versions'),
    sa.ForeignKeyConstraint(['experiment_id'], ['experiments.experiment_id'], name='fk_runs_experiment'),
    sa.PrimaryKeyConstraint('run_id', name=op.f('pk_runs'))
    )
    op.create_index('ix_runs_experiment', 'runs', ['experiment_id'], unique=False)
    op.create_table('events',
    sa.Column('event_id', sa.String(length=128), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('seq', sa.BigInteger(), nullable=False),
    sa.Column('type', sa.String(length=64), nullable=False),
    sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('sim_time_ms', sa.BigInteger(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('correlation_id', sa.String(length=128), nullable=False),
    sa.Column('causation_id', sa.String(length=128), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.CheckConstraint("type IN ('RunStarted', 'RunPaused', 'RunResumed', 'RunStopped', 'NoticePublished', 'LocationClosed', 'ActivityTimeChanged', 'AgentObserved', 'DecisionRequested', 'DecisionRecorded', 'ActionStarted', 'AgentArrived', 'MessageDelivered', 'ActionInterrupted', 'ActionRejected')", name='ck_events_type'),
    sa.CheckConstraint('seq > 0 AND schema_version > 0 AND sim_time_ms >= 0', name='ck_events_versions'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.run_id'], name='fk_events_run'),
    sa.PrimaryKeyConstraint('event_id', name=op.f('pk_events')),
    sa.UniqueConstraint('run_id', 'event_id', name='uq_events_run_event'),
    sa.UniqueConstraint('run_id', 'seq', name='uq_events_run_seq')
    )
    op.create_index('ix_events_correlation', 'events', ['correlation_id'], unique=False)
    op.create_index('ix_events_run_sim_time', 'events', ['run_id', 'sim_time_ms', 'seq'], unique=False)
    op.create_table('location_states',
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('location_id', sa.String(length=128), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('is_open', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=True),
    sa.Column('resource_version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('state', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.CheckConstraint('capacity IS NULL OR capacity >= 0', name='ck_location_states_capacity'),
    sa.CheckConstraint('resource_version >= 0', name='ck_location_states_version'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.run_id'], name='fk_location_states_run'),
    sa.PrimaryKeyConstraint('run_id', 'location_id', name=op.f('pk_location_states'))
    )
    op.create_table('snapshots',
    sa.Column('snapshot_id', sa.String(length=128), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('seq', sa.BigInteger(), nullable=False),
    sa.Column('sim_time_ms', sa.BigInteger(), nullable=False),
    sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('world_state', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('canonical_hash', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('seq >= 0 AND sim_time_ms >= 0 AND schema_version > 0', name='ck_snapshots_versions'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.run_id'], name='fk_snapshots_run'),
    sa.PrimaryKeyConstraint('snapshot_id', name=op.f('pk_snapshots')),
    sa.UniqueConstraint('run_id', 'seq', 'sim_time_ms', name='uq_snapshots_run_cursor')
    )
    op.create_index('ix_snapshots_run_sim_time', 'snapshots', ['run_id', 'sim_time_ms'], unique=False)
    op.create_table('activities',
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('activity_id', sa.String(length=128), nullable=False),
    sa.Column('location_id', sa.String(length=128), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('starts_at_ms', sa.BigInteger(), nullable=False),
    sa.Column('ends_at_ms', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='scheduled', nullable=False),
    sa.Column('resource_version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('participants', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('state', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.CheckConstraint("status IN ('scheduled','active','finished','cancelled')", name='ck_activities_status'),
    sa.CheckConstraint('resource_version >= 0', name='ck_activities_version'),
    sa.CheckConstraint('starts_at_ms >= 0 AND ends_at_ms >= starts_at_ms', name='ck_activities_schedule'),
    sa.ForeignKeyConstraint(['run_id', 'location_id'], ['location_states.run_id', 'location_states.location_id'], name='fk_activities_location_in_run'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.run_id'], name='fk_activities_run'),
    sa.PrimaryKeyConstraint('run_id', 'activity_id', name=op.f('pk_activities'))
    )
    op.create_index('ix_activities_run_schedule', 'activities', ['run_id', 'starts_at_ms'], unique=False)
    op.create_table('commands',
    sa.Column('command_id', sa.String(length=128), nullable=False),
    sa.Column('request_id', sa.String(length=128), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('type', sa.String(length=64), nullable=False),
    sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
    sa.Column('correlation_id', sa.String(length=128), nullable=False),
    sa.Column('causation_id', sa.String(length=128), nullable=True),
    sa.Column('result_event_id', sa.String(length=128), nullable=True),
    sa.Column('rejection_reason', sa.Text(), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('pending','applied','rejected')", name='ck_commands_status'),
    sa.CheckConstraint("type IN ('ValidateConfig', 'StartRun', 'PauseRun', 'ResumeRun', 'StopRun', 'PublishNotice', 'CloseLocation', 'ChangeActivityTime', 'ProposeAction', 'CompleteAction')", name='ck_commands_type'),
    sa.CheckConstraint('schema_version > 0', name='ck_commands_schema_version'),
    sa.ForeignKeyConstraint(['run_id', 'result_event_id'], ['events.run_id', 'events.event_id'], name='fk_commands_result_event_in_run'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.run_id'], name='fk_commands_run'),
    sa.PrimaryKeyConstraint('command_id', name=op.f('pk_commands')),
    sa.UniqueConstraint('request_id', name='uq_commands_request_id')
    )
    op.create_index('ix_commands_run_pending', 'commands', ['run_id', 'status', 'received_at', 'command_id'], unique=False)
    op.create_table('consumer_receipts',
    sa.Column('consumer_name', sa.String(length=128), nullable=False),
    sa.Column('event_id', sa.String(length=128), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['run_id', 'event_id'], ['events.run_id', 'events.event_id'], name='fk_consumer_receipts_event_in_run'),
    sa.PrimaryKeyConstraint('consumer_name', 'event_id', name='pk_consumer_receipts')
    )
    op.create_index('ix_consumer_receipts_run', 'consumer_receipts', ['run_id'], unique=False)
    op.create_table('outbox',
    sa.Column('outbox_id', sa.String(length=128), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('event_id', sa.String(length=128), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('attempts >= 0', name='ck_outbox_attempts'),
    sa.ForeignKeyConstraint(['run_id', 'event_id'], ['events.run_id', 'events.event_id'], name='fk_outbox_event_in_run'),
    sa.PrimaryKeyConstraint('outbox_id', name=op.f('pk_outbox')),
    sa.UniqueConstraint('event_id', name='uq_outbox_event_id')
    )
    op.create_index('ix_outbox_unpublished', 'outbox', ['next_attempt_at', 'run_id'], unique=False, postgresql_where=sa.text('published_at IS NULL'))
    op.create_table('agent_states',
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('agent_id', sa.String(length=128), nullable=False),
    sa.Column('location_id', sa.String(length=128), nullable=True),
    sa.Column('activity_id', sa.String(length=128), nullable=True),
    sa.Column('plan_version', sa.Integer(), server_default='0', nullable=False),
    sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('position', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('action_id', sa.String(length=128), nullable=True),
    sa.Column('action_type', sa.String(length=32), nullable=True),
    sa.Column('action_payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('action_started_at_ms', sa.BigInteger(), nullable=True),
    sa.Column('action_ends_at_ms', sa.BigInteger(), nullable=True),
    sa.Column('state', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.CheckConstraint("action_type IS NULL OR action_type IN ('MOVE','TALK','WAIT','JOIN_ACTIVITY')", name='ck_agent_states_action_type'),
    sa.CheckConstraint('(action_started_at_ms IS NULL OR action_started_at_ms >= 0) AND (action_ends_at_ms IS NULL OR action_ends_at_ms >= 0) AND (action_started_at_ms IS NULL OR action_ends_at_ms IS NULL OR action_ends_at_ms >= action_started_at_ms)', name='ck_agent_states_action_time'),
    sa.CheckConstraint('plan_version >= 0', name='ck_agent_states_plan_version'),
    sa.ForeignKeyConstraint(['run_id', 'activity_id'], ['activities.run_id', 'activities.activity_id'], name='fk_agent_states_activity_in_run'),
    sa.ForeignKeyConstraint(['run_id', 'location_id'], ['location_states.run_id', 'location_states.location_id'], name='fk_agent_states_location_in_run'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.run_id'], name='fk_agent_states_run'),
    sa.PrimaryKeyConstraint('run_id', 'agent_id', name=op.f('pk_agent_states'))
    )
    op.create_table('decision_jobs',
    sa.Column('job_id', sa.String(length=128), nullable=False),
    sa.Column('task_key', sa.String(length=255), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('agent_id', sa.String(length=128), nullable=False),
    sa.Column('source_event_id', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('run_epoch', sa.Integer(), nullable=False),
    sa.Column('agent_plan_version', sa.Integer(), nullable=False),
    sa.Column('context_event_seq', sa.BigInteger(), nullable=False),
    sa.Column('input_context_versions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('input_context', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('needs_reevaluation', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('claimed_by', sa.String(length=128), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error_code', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending','running','completed','failed','cancelled')", name='ck_decision_jobs_status'),
    sa.CheckConstraint('run_epoch >= 0 AND agent_plan_version >= 0 AND context_event_seq >= 0 AND attempts >= 0', name='ck_decision_jobs_versions_attempts'),
    sa.ForeignKeyConstraint(['run_id', 'agent_id'], ['agent_states.run_id', 'agent_states.agent_id'], name='fk_decision_jobs_agent_in_run'),
    sa.ForeignKeyConstraint(['run_id', 'source_event_id'], ['events.run_id', 'events.event_id'], name='fk_decision_jobs_source_event_in_run'),
    sa.PrimaryKeyConstraint('job_id', name=op.f('pk_decision_jobs')),
    sa.UniqueConstraint('run_id', 'job_id', name='uq_decision_jobs_run_job'),
    sa.UniqueConstraint('task_key', name='uq_decision_jobs_task_key')
    )
    op.create_index('ix_decision_jobs_pending', 'decision_jobs', ['status', 'next_attempt_at'], unique=False)
    op.create_index('uq_decision_jobs_unfinished_agent', 'decision_jobs', ['run_id', 'agent_id'], unique=True, postgresql_where=sa.text("status IN ('pending','running')"))
    op.create_table('memories',
    sa.Column('memory_id', sa.String(length=128), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('agent_id', sa.String(length=128), nullable=False),
    sa.Column('source_event_id', sa.String(length=128), nullable=False),
    sa.Column('sim_time_ms', sa.BigInteger(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('importance', sa.Integer(), server_default='0', nullable=False),
    sa.Column('topics', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('sim_time_ms >= 0 AND importance >= 0', name='ck_memories_values'),
    sa.ForeignKeyConstraint(['run_id', 'agent_id'], ['agent_states.run_id', 'agent_states.agent_id'], name='fk_memories_agent_in_run'),
    sa.ForeignKeyConstraint(['run_id', 'source_event_id'], ['events.run_id', 'events.event_id'], name='fk_memories_source_event_in_run'),
    sa.PrimaryKeyConstraint('memory_id', name=op.f('pk_memories'))
    )
    op.create_index('ix_memories_agent_time', 'memories', ['run_id', 'agent_id', 'sim_time_ms'], unique=False)
    op.create_index('ix_memories_source_event', 'memories', ['run_id', 'source_event_id'], unique=False)
    op.create_table('model_calls',
    sa.Column('call_id', sa.String(length=128), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('job_id', sa.String(length=128), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('provider', sa.String(length=128), nullable=True),
    sa.Column('model_name', sa.String(length=200), nullable=True),
    sa.Column('model_version', sa.String(length=128), nullable=True),
    sa.Column('prompt_version', sa.String(length=128), nullable=True),
    sa.Column('request_status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('attempt', sa.Integer(), server_default='1', nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('latency_ms', sa.BigInteger(), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=True),
    sa.Column('output_tokens', sa.Integer(), nullable=True),
    sa.Column('error_code', sa.String(length=128), nullable=True),
    sa.CheckConstraint("request_status IN ('pending','running','succeeded','failed','timed_out','cancelled')", name='ck_model_calls_request_status'),
    sa.CheckConstraint("source IN ('model','rule')", name='ck_model_calls_source'),
    sa.CheckConstraint('attempt >= 1 AND (latency_ms IS NULL OR latency_ms >= 0) AND (input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0)', name='ck_model_calls_metrics'),
    sa.ForeignKeyConstraint(['run_id', 'job_id'], ['decision_jobs.run_id', 'decision_jobs.job_id'], name='fk_model_calls_job_in_run'),
    sa.PrimaryKeyConstraint('call_id', name=op.f('pk_model_calls'))
    )
    op.create_index('ix_model_calls_job', 'model_calls', ['run_id', 'job_id'], unique=False)
    op.create_index('ix_model_calls_run_started', 'model_calls', ['run_id', 'started_at'], unique=False)


def downgrade() -> None:
    """Remove dependent objects first; keep the phase-one baseline revision."""
    op.drop_index('ix_model_calls_run_started', table_name='model_calls')
    op.drop_index('ix_model_calls_job', table_name='model_calls')
    op.drop_table('model_calls')
    op.drop_index('ix_memories_source_event', table_name='memories')
    op.drop_index('ix_memories_agent_time', table_name='memories')
    op.drop_table('memories')
    op.drop_index('uq_decision_jobs_unfinished_agent', table_name='decision_jobs', postgresql_where=sa.text("status IN ('pending','running')"))
    op.drop_index('ix_decision_jobs_pending', table_name='decision_jobs')
    op.drop_table('decision_jobs')
    op.drop_table('agent_states')
    op.drop_index('ix_outbox_unpublished', table_name='outbox', postgresql_where=sa.text('published_at IS NULL'))
    op.drop_table('outbox')
    op.drop_index('ix_consumer_receipts_run', table_name='consumer_receipts')
    op.drop_table('consumer_receipts')
    op.drop_index('ix_commands_run_pending', table_name='commands')
    op.drop_table('commands')
    op.drop_index('ix_activities_run_schedule', table_name='activities')
    op.drop_table('activities')
    op.drop_index('ix_snapshots_run_sim_time', table_name='snapshots')
    op.drop_table('snapshots')
    op.drop_table('location_states')
    op.drop_index('ix_events_run_sim_time', table_name='events')
    op.drop_index('ix_events_correlation', table_name='events')
    op.drop_table('events')
    op.drop_index('ix_runs_experiment', table_name='runs')
    op.drop_table('runs')
    op.drop_index('ix_agent_profiles_experiment', table_name='agent_profiles')
    op.drop_table('agent_profiles')
    op.drop_table('experiments')
