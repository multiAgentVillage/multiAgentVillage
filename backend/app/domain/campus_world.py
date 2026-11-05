"""The minimal Command receiver: publishing a notice changes history only.

This is deliberately a small implementation of the existing World contract.
Movement, lifecycle commands and history restoration remain outside stage three.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.commands import (
    ChangeActivityTimeCommand, CloseLocationCommand, CommandKind,
    CompleteActionCommand, PauseRunCommand, ProposeActionCommand,
    PublishNoticeCommand, ResumeRunCommand, StartRunCommand, StopRunCommand,
    ValidateConfigCommand, WorldCommand,
)
from app.domain.errors import CommandRejected
from app.domain.events import DomainEvent, EventDraft, EventType
from app.domain.memento import WorldMemento
from app.domain.run_states import Disposition, RunStatus
from app.domain.world import ValidationResult


@dataclass(frozen=True)
class NoticeRunState:
    """GoF State for this slice; other command authorizations are not implemented."""

    status: RunStatus

    def classify(self, kind: CommandKind) -> Disposition:
        if kind != CommandKind.PUBLISH_NOTICE:
            return Disposition.REJECT
        if self.status == RunStatus.RUNNING:
            return Disposition.EXECUTE
        # A notice is a new intervention, not a completed action proposal.
        # Reject it while paused so resuming cannot apply a surprise notice.
        return Disposition.REJECT

    def transition(self, kind: CommandKind) -> RunStatus:
        # Publishing a notice never performs a lifecycle transition.
        if kind != CommandKind.PUBLISH_NOTICE:
            raise NotImplementedError("Lifecycle transitions are outside this slice")
        return self.status

    def can_advance(self) -> bool:
        return self.status == RunStatus.RUNNING


@dataclass
class CampusWorld:
    run_id: str
    status: RunStatus
    sim_time_ms: int
    run_epoch: int
    last_seq: int
    agent_ids: tuple[str, ...]

    @property
    def state(self) -> NoticeRunState:
        return NoticeRunState(self.status)

    def validate(self, command: WorldCommand) -> ValidationResult:
        if command.run_id != self.run_id:
            return ValidationResult(allowed=False, reason="命令不属于当前运行")
        if self.state.classify(command.kind) != Disposition.EXECUTE:
            return ValidationResult(allowed=False, reason=f"运行状态{self.status.value}不允许发布通知")
        if not isinstance(command, PublishNoticeCommand):
            return ValidationResult(allowed=False, reason="本阶段仅支持PublishNotice")
        if not command.content.strip():
            return ValidationResult(allowed=False, reason="通知内容不能为空")
        if len(command.content) > 2000:
            return ValidationResult(allowed=False, reason="通知内容不能超过2000字符")
        if not self.agent_ids:
            return ValidationResult(allowed=False, reason="当前运行没有可接收通知的角色")
        if set(command.recipient_agent_ids) - set(self.agent_ids):
            return ValidationResult(allowed=False, reason="通知收件人不属于当前运行")
        return ValidationResult(allowed=True)

    def publish_notice(self, command: PublishNoticeCommand) -> tuple[EventDraft, ...]:
        validation = self.validate(command)
        if not validation.allowed:
            raise CommandRejected(validation.reason or "通知被拒绝")
        requested = set(command.recipient_agent_ids)
        recipients = [agent_id for agent_id in self.agent_ids if not requested or agent_id in requested]
        return (EventDraft(
            run_id=self.run_id, type=EventType.NOTICE_PUBLISHED,
            sim_time_ms=self.sim_time_ms, occurred_at=datetime.now(timezone.utc),
            correlation_id=command.command_id, causation_id=command.command_id,
            payload={"content": command.content, "recipient_agent_ids": recipients},
        ),)

    def record_rejection(self, command: WorldCommand, reason: str) -> tuple[EventDraft, ...]:
        # Invalid notice commands are persisted as rejected command results, not
        # recursively emitted as operational failure events (plan section 3.3).
        return ()

    def validate_config(self, command: ValidateConfigCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Configuration commands are not implemented")

    def start_run(self, command: StartRunCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Lifecycle commands are not implemented")

    def pause_run(self, command: PauseRunCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Lifecycle commands are not implemented")

    def resume_run(self, command: ResumeRunCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Lifecycle commands are not implemented")

    def stop_run(self, command: StopRunCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Lifecycle commands are not implemented")

    def create_memento(self) -> WorldMemento:
        raise NotImplementedError("History snapshots are not implemented")

    @classmethod
    def from_memento(cls, memento: WorldMemento, *, read_only: bool) -> "CampusWorld":
        raise NotImplementedError("History restoration is not implemented")

    def apply_event(self, event: DomainEvent) -> None:
        raise NotImplementedError("History replay is not implemented")

    def close_location(self, command: CloseLocationCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Location commands are not implemented")

    def change_activity_time(self, command: ChangeActivityTimeCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Activity commands are not implemented")

    def propose_action(self, command: ProposeActionCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Agent actions are not implemented")

    def complete_action(self, command: CompleteActionCommand) -> tuple[EventDraft, ...]:
        raise NotImplementedError("Agent actions are not implemented")
