"""GoF Strategy interface; concrete decision algorithms are deferred."""
from typing import Protocol

from app.domain.decisions import ActionProposal, DecisionContext


class DecisionStrategy(Protocol):
    async def decide(self, context: DecisionContext) -> ActionProposal: ...


class RuleDecisionStrategy:
    async def decide(self, context: DecisionContext) -> ActionProposal:
        raise NotImplementedError("RuleDecisionStrategy is not implemented in phase one")
