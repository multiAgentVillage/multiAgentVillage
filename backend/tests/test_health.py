"""Verify the public readiness contract and lifecycle without external services."""
from fastapi.testclient import TestClient

from app.api import main
from app.config import Settings


class FakeResources:
    def __init__(self, dependencies: dict[str, str]):
        self.dependencies = dependencies
        self.closed = False

    async def readiness(self) -> dict[str, str]:
        return self.dependencies

    async def close(self) -> None:
        self.closed = True


def test_ready_and_lifecycle(monkeypatch):
    resources = FakeResources({"postgres": "ok", "redis": "ok"})
    monkeypatch.setattr(main, "build_resources", lambda settings: resources)
    with TestClient(main.create_app(Settings(_env_file=None), start_consumers=False)) as client:
        assert client.get("/health/live").json() == {"status": "ok", "service": "api"}
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "dependencies": resources.dependencies}
    assert resources.closed


def test_unavailable_dependency_is_not_ready(monkeypatch):
    resources = FakeResources({"postgres": "unavailable", "redis": "ok"})
    monkeypatch.setattr(main, "build_resources", lambda settings: resources)
    with TestClient(main.create_app(Settings(_env_file=None), start_consumers=False)) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready", "dependencies": resources.dependencies}
    assert resources.closed
