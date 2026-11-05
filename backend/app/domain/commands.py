"""GoF Command DTOs and wire envelope; execute only forwards to World."""
from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Protocol, TYPE_CHECKING

from pydantic import StrictStr

from app.domain.contract_types import (
    ContractModel, FrozenJsonObject, Identifier, NonNegativeInt, PositiveInt,
)
from app.domain.decisions import ActionProposal
from app.domain.events import EventDraft

if TYPE_CHECKING:
    from app.domain.world import World


class CommandKind(StrEnum):
    VALIDATE_CONFIG = "ValidateConfig"
    START = "StartRun"
    PAUSE = "PauseRun"
    RESUME = "ResumeRun"
    STOP = "StopRun"
    PUBLISH_NOTICE = "PublishNotice"
    CLOSE_LOCATION = "CloseLocation"
    CHANGE_ACTIVITY_TIME = "ChangeActivityTime"
    PROPOSE_ACTION = "ProposeAction"
    COMPLETE_ACTION = "CompleteAction"


class CommandStatus(StrEnum):
    ACCEPTED = "accepted"
    PENDING = "pending"
    DEFERRED = "deferred"
    APPLIED = "applied"
    REJECTED = "rejected"


class CommandEnvelope(ContractModel):
    command_id: Identifier
    request_id: Identifier
    run_id: Identifier
    type: CommandKind
    schema_version: PositiveInt = 1
    payload: FrozenJsonObject

    @property
    def kind(self) -> CommandKind:
        return self.type


class CommandReceipt(ContractModel):
    """Accepted confirms persistence only; applied confirms the world commit."""

    command_id: Identifier
    status: CommandStatus
    result_event_ids: tuple[Identifier, ...] = ()
    reason: StrictStr | None = None


class WorldCommand(Protocol):
    @property
    def command_id(self) -> str: ...
    @property
    def run_id(self) -> str: ...
    @property
    def kind(self) -> CommandKind: ...
    def execute(self, world: World) -> tuple[EventDraft, ...]: ...


class _CommandData(ContractModel):
    """Decoded command data; not the persistence or transport envelope."""

    command_id: Identifier
    run_id: Identifier
    kind: ClassVar[CommandKind]


class ValidateConfigCommand(_CommandData):
    kind = CommandKind.VALIDATE_CONFIG

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.validate_config(self)


class StartRunCommand(_CommandData):
    kind = CommandKind.START

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.start_run(self)


class PauseRunCommand(_CommandData):
    kind = CommandKind.PAUSE

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.pause_run(self)


class ResumeRunCommand(_CommandData):
    kind = CommandKind.RESUME

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.resume_run(self)


class StopRunCommand(_CommandData):
    kind = CommandKind.STOP

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.stop_run(self)


class PublishNoticeCommand(_CommandData):
    kind = CommandKind.PUBLISH_NOTICE
    content: Identifier
    recipient_agent_ids: tuple[Identifier, ...] = ()

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.publish_notice(self)


class CloseLocationCommand(_CommandData):
    kind = CommandKind.CLOSE_LOCATION
    location_id: Identifier
    reason: Identifier

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.close_location(self)


class ChangeActivityTimeCommand(_CommandData):
    kind = CommandKind.CHANGE_ACTIVITY_TIME
    activity_id: Identifier
    starts_at_sim_time_ms: NonNegativeInt
    ends_at_sim_time_ms: NonNegativeInt
    reason: Identifier

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.change_activity_time(self)


class ProposeActionCommand(_CommandData):
    kind = CommandKind.PROPOSE_ACTION
    run_epoch: NonNegativeInt
    agent_plan_version: NonNegativeInt
    resource_revisions: tuple[tuple[Identifier, NonNegativeInt], ...]
    proposal: ActionProposal
    expires_at_sim_time_ms: NonNegativeInt

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.propose_action(self)


class CompleteActionCommand(_CommandData):
    kind = CommandKind.COMPLETE_ACTION
    action_id: Identifier
    agent_id: Identifier
    run_epoch: NonNegativeInt
    agent_plan_version: NonNegativeInt
    due_sim_time_ms: NonNegativeInt

    def execute(self, world: World) -> tuple[EventDraft, ...]:
        return world.complete_action(self)
