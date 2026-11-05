"""Strategy context placeholder; no task claiming or model calls yet."""
from app.domain.decisions import ActionProposal, DecisionContext
from app.domain.strategies import DecisionStrategy


class DecisionService:
    def __init__(self, preferred: DecisionStrategy, fallback: DecisionStrategy) -> None:
        self.preferred = preferred
        self.fallback = fallback

    async def decide(self, context: DecisionContext) -> ActionProposal:
        raise NotImplementedError("DecisionService is not implemented in phase one")
