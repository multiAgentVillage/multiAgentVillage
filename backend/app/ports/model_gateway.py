"""Adapter target: provider-neutral model request/response contracts."""
from typing import Protocol

from pydantic import StrictStr

from app.domain.contract_types import ContractModel, NonNegativeInt, PositiveInt


class ModelUnavailable(Exception):
    """ProviderAdapter maps retryable provider/network failures to this error."""


class InvalidModelOutput(Exception):
    """DecisionStrategy reports invalid structured action output separately."""


class ModelRequest(ContractModel):
    prompt: StrictStr
    max_output_tokens: PositiveInt


class ModelResponse(ContractModel):
    text: StrictStr
    input_tokens: NonNegativeInt | None
    output_tokens: NonNegativeInt | None


class ModelGateway(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...
