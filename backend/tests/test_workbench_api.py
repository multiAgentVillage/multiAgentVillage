"""Exercise the public transport contract separately from transaction tests."""
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.api.main import create_app
from app.api.workbench import facade, queries
from app.application.workbench import EventPage, RunSummary, RunView
from app.domain.commands import CommandReceipt
from app.domain.events import DomainEvent
from app.infrastructure.postgres.repositories import RequestConflict, RunNotFound


class Queries:
    async def list_runs(self):
        return (RunSummary(run_id="run-1", name="演示", status="RUNNING", sim_time_ms=0, last_seq=2),)

    async def state(self, run_id):
        if run_id == "missing":
            raise RunNotFound(run_id)
        return RunView(**(await self.list_runs())[0].model_dump(), locations=(), agents=())

    async def events(self, run_id, after_seq, limit):
        items = tuple(DomainEvent(
            event_id=f"evt-{seq}", run_id=run_id, seq=seq, type="NoticePublished",
            sim_time_ms=0, occurred_at="2026-11-05T00:00:00Z",
            correlation_id="cmd-1", causation_id="cmd-1",
            payload={"content": "活动通知", "recipient_agent_ids": ["chen-yu"]},
        ) for seq in range(after_seq + 1, min(3, after_seq + limit + 1)))
        return EventPage(items=items, next_seq=items[-1].seq if items else after_seq,
                         has_more=bool(items and items[-1].seq < 2))


class Facade:
    async def submit(self, envelope):
        if envelope.request_id == "conflict":
            raise RequestConflict()
        return CommandReceipt(command_id=envelope.command_id, status="accepted")


@pytest_asyncio.fixture
async def client():
    app = create_app(start_consumers=False)
    app.dependency_overrides[queries] = lambda: Queries()
    app.dependency_overrides[facade] = lambda: Facade()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_submission_returns_accepted_without_claiming_effective(client):
    response = await client.post("/runs/run-1/commands", json={
        "request_id": uuid4().hex, "type": "PublishNotice",
        "payload": {"content": "活动通知", "recipient_agent_ids": []},
    })
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["result_event_ids"] == []
    assert response.json()["command_id"].startswith("cmd-")


async def test_request_conflict_has_explicit_http_feedback(client):
    response = await client.post("/runs/run-1/commands", json={
        "request_id": "conflict", "type": "PublishNotice", "payload": {"content": "changed"},
    })
    assert response.status_code == 409
    assert "不同内容" in response.json()["detail"]


async def test_incremental_page_uses_wire_envelope_and_client_cursor(client):
    first = await client.get("/runs/run-1/events?after_seq=0&limit=1")
    assert first.status_code == 200
    assert first.json()["next_seq"] == 1 and first.json()["has_more"]
    event = first.json()["items"][0]
    assert event["type"] == "NoticePublished" and isinstance(event["payload"], dict)
    assert event["causation_id"] == "cmd-1"
    second = (await client.get("/runs/run-1/events?after_seq=1&limit=1")).json()
    assert [item["seq"] for item in second["items"]] == [2]
    empty = (await client.get("/runs/run-1/events?after_seq=2")).json()
    assert empty == {"items": [], "next_seq": 2, "has_more": False}


@pytest.mark.parametrize("suffix", ["after_seq=-1", "limit=0", "limit=201"])
async def test_incremental_parameters_are_bounded(client, suffix):
    assert (await client.get(f"/runs/run-1/events?{suffix}")).status_code == 422


async def test_missing_run_is_404(client):
    assert (await client.get("/runs/missing/state")).status_code == 404


async def test_unknown_command_is_validation_error(client):
    response = await client.post("/runs/run-1/commands", json={
        "request_id": "req-1", "type": "ExecuteAnything", "payload": {},
    })
    assert response.status_code == 422


async def test_run_list_and_state_are_serializable(client):
    assert (await client.get("/runs")).json()["items"][0]["run_id"] == "run-1"
    assert (await client.get("/runs/run-1/state")).json()["status"] == "RUNNING"
