"""Model provider placeholders: no external API requests or fake success results."""
from app.ports.model_gateway import ModelRequest, ModelResponse


class ProviderAdapter:
    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError("Select and implement a provider in the model-integration phase")


class FakeModelGateway:
    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError("Supply an explicit deterministic response in tests")
