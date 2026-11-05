"""Validated strategy input/output; no perception or decision algorithms."""
from enum import StrEnum
from typing import Literal

from pydantic import StrictBool, StrictStr

from app.domain.contract_types import ContractModel, Identifier, NonNegativeInt


class ActionType(StrEnum):
    MOVE = "MOVE"
    TALK = "TALK"
    WAIT = "WAIT"
    JOIN_ACTIVITY = "JOIN_ACTIVITY"


class DecisionContext(ContractModel):
    run_id: Identifier
    agent_id: Identifier
    run_epoch: NonNegativeInt
    agent_plan_version: NonNegativeInt
    visible_facts: tuple[StrictStr, ...]
    model_allowed: StrictBool


class ActionProposal(ContractModel):
    agent_id: Identifier
    action: ActionType
    target: Identifier | None
    source: Literal["model", "rule"]
    summary: StrictStr
    memory_refs: tuple[Identifier, ...] = ()
