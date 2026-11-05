"""State contract only; concrete state authorization is not implemented yet."""
from enum import StrEnum
from typing import Protocol

from app.domain.commands import CommandKind


class RunStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


class Disposition(StrEnum):
    EXECUTE = "execute"
    DEFER = "defer"
    REJECT = "reject"


class RunState(Protocol):
    def classify(self, kind: CommandKind) -> Disposition: ...
    def transition(self, kind: CommandKind) -> RunStatus: ...
    def can_advance(self) -> bool: ...
