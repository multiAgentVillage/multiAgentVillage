"""Section 3.3 event v1 contracts; sequencing belongs to CommandProcessor."""
from enum import StrEnum

from pydantic import field_validator

from app.domain.contract_types import (
    ContractModel, FrozenJsonObject, Identifier, NonNegativeInt, PositiveInt,
    UtcTimestamp, as_utc,
)


class EventType(StrEnum):
    RUN_STARTED = "RunStarted"
    RUN_PAUSED = "RunPaused"
    RUN_RESUMED = "RunResumed"
    RUN_STOPPED = "RunStopped"
    NOTICE_PUBLISHED = "NoticePublished"
    LOCATION_CLOSED = "LocationClosed"
    ACTIVITY_TIME_CHANGED = "ActivityTimeChanged"
    AGENT_OBSERVED = "AgentObserved"
    DECISION_REQUESTED = "DecisionRequested"
    DECISION_RECORDED = "DecisionRecorded"
    ACTION_STARTED = "ActionStarted"
    AGENT_ARRIVED = "AgentArrived"
    MESSAGE_DELIVERED = "MessageDelivered"
    ACTION_INTERRUPTED = "ActionInterrupted"
    ACTION_REJECTED = "ActionRejected"


class EventDraft(ContractModel):
    """World output before CommandProcessor allocates event_id and run-local seq."""

    run_id: Identifier
    type: EventType
    schema_version: PositiveInt = 1
    sim_time_ms: NonNegativeInt
    occurred_at: UtcTimestamp
    correlation_id: Identifier
    causation_id: Identifier
    payload: FrozenJsonObject

    _normalize_time = field_validator("occurred_at")(as_utc)

    @property
    def kind(self) -> EventType:
        """Internal compatibility name; wire data always uses type."""
        return self.type


class DomainEvent(EventDraft):
    """Committed immutable fact; (run_id, seq) is its ordering key."""

    event_id: Identifier
    seq: PositiveInt
