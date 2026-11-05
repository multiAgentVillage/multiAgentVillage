"""LLMDecisionStrategy placeholder, with provider dependency injected via a port."""
from collections.abc import Callable

from app.domain.decisions import ActionProposal, DecisionContext
from app.ports.model_gateway import ModelGateway, ModelRequest, ModelResponse


class LLMDecisionStrategy:
    def __init__(
        self, gateway: ModelGateway,
        build_request: Callable[[DecisionContext], ModelRequest],
        parse_proposal: Callable[[ModelResponse, DecisionContext], ActionProposal],
    ) -> None:
        self.gateway = gateway
        self.build_request = build_request
        self.parse_proposal = parse_proposal

    async def decide(self, context: DecisionContext) -> ActionProposal:
        raise NotImplementedError("LLMDecisionStrategy is not implemented in phase one")
