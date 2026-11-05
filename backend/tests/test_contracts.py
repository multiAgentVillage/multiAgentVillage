"""Freeze public v1 message shapes and the dependency direction of GoF contracts."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from app.domain import commands
from app.domain.commands import CloseLocationCommand, CommandEnvelope, CommandKind
from app.domain.contract_types import FrozenJsonObject
from app.domain.decisions import ActionProposal
from app.domain.events import DomainEvent, EventDraft, EventType
from app.domain.memento import ReadOnlyView, WorldMemento
from app.domain.run_states import RunStatus
from app.domain.world import World


EVENT_EXAMPLE = {
    "event_id": "evt-00042",
    "run_id": "run-001",
    "seq": 42,
    "type": "LocationClosed",
    "schema_version": 1,
    "sim_time_ms": 420000,
    "occurred_at": "2026-11-02T02:00:00Z",
    "correlation_id": "trace-007",
    "causation_id": "cmd-007",
    "payload": {"location_id": "activity-room", "reason": "临时维护"},
}
COMMAND_EXAMPLE = {
    "command_id": "cmd-007", "request_id": "request-007", "run_id": "run-001",
    "type": "CloseLocation", "schema_version": 1,
    "payload": {"location_id": "activity-room", "reason": "临时维护"},
}


def test_plan_event_json_roundtrip_and_wire_names() -> None:
    event = DomainEvent.model_validate_json(json.dumps(EVENT_EXAMPLE))
    assert event.model_dump(mode="json") == EVENT_EXAMPLE
    assert json.loads(event.model_dump_json()) == EVENT_EXAMPLE
    assert event.type is EventType.LOCATION_CLOSED
    assert event.kind is EventType.LOCATION_CLOSED
    assert event.occurred_at.tzinfo is timezone.utc
    assert "kind" not in event.model_dump()
    assert "payload_json" not in event.model_dump()
    assert DomainEvent.model_validate(event.model_dump()) == event


def test_event_draft_excludes_unallocated_fields() -> None:
    values = {key: value for key, value in EVENT_EXAMPLE.items() if key not in {"seq", "event_id"}}
    draft = EventDraft.model_validate(values)
    assert set(draft.model_dump()) == set(values)
    with pytest.raises(ValidationError):
        EventDraft.model_validate(EVENT_EXAMPLE)


@pytest.mark.parametrize("kind", list(EventType))
def test_all_core_event_types_validate(kind: EventType) -> None:
    assert DomainEvent.model_validate(EVENT_EXAMPLE | {"type": kind.value}).type is kind


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seq", 0), ("seq", -1), ("seq", True), ("seq", "42"), ("seq", 1.0),
        ("sim_time_ms", -1), ("sim_time_ms", False), ("schema_version", 0),
        ("schema_version", "1"), ("type", "UnknownEvent"), ("type", 4),
        ("event_id", ""), ("run_id", 7), ("correlation_id", None),
        ("causation_id", ""), ("payload", []), ("payload", "{}"),
        ("payload", {"bad": object()}), ("payload", {"bad": float("nan")}),
        ("payload", {"bad": float("inf")}), ("payload", {1: "wrong-key"}),
        ("occurred_at", "2026-11-02T02:00:00"),
        ("occurred_at", datetime(2026, 11, 2, 2)),
        ("occurred_at", 1234567890), ("unexpected", "extra"),
    ],
)
def test_invalid_event_fields_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        DomainEvent.model_validate(EVENT_EXAMPLE | {field: value})


def test_aware_timestamps_normalize_to_utc() -> None:
    offset = datetime(2026, 11, 2, 10, tzinfo=timezone(timedelta(hours=8)))
    event = DomainEvent.model_validate(EVENT_EXAMPLE | {"occurred_at": offset})
    assert event.model_dump(mode="json")["occurred_at"] == EVENT_EXAMPLE["occurred_at"]


def test_event_and_payload_are_recursively_frozen_and_detached() -> None:
    source = {"nested": {"items": [{"text": "original"}]}, "primitives": [None, True, 3, 0.5]}
    event = DomainEvent.model_validate(EVENT_EXAMPLE | {"payload": source})
    source["nested"]["items"][0]["text"] = "external mutation"
    assert event.payload["nested"]["items"][0]["text"] == "original"
    with pytest.raises(ValidationError):
        event.seq = 99
    with pytest.raises(TypeError):
        event.payload["new"] = 1
    with pytest.raises(TypeError):
        event.payload["nested"]["items"][0]["text"] = "mutation"
    with pytest.raises(AttributeError):
        event.payload["nested"]["items"].append(1)
    detached = event.model_dump(mode="json")
    detached["payload"]["nested"]["items"][0]["text"] = "serialized mutation"
    assert event.payload["nested"]["items"][0]["text"] == "original"
    assert DomainEvent.model_validate_json(event.model_dump_json()) == event


def test_json_cycles_are_rejected_without_recursion_error() -> None:
    payload: dict[str, object] = {}
    payload["self"] = payload
    with pytest.raises(ValidationError, match="cycles"):
        DomainEvent.model_validate(EVENT_EXAMPLE | {"payload": payload})


@pytest.mark.parametrize("kind", list(CommandKind))
def test_command_envelope_roundtrip_and_whitelist(kind: CommandKind) -> None:
    values = COMMAND_EXAMPLE | {"type": kind.value}
    command = CommandEnvelope.model_validate_json(json.dumps(values))
    assert command.model_dump(mode="json") == values
    assert command.kind is kind
    assert "kind" not in command.model_dump()
    assert isinstance(command.payload, FrozenJsonObject)


@pytest.mark.parametrize(
    ("field", "value"),
    [("type", "ImportPythonClass"), ("type", 9), ("schema_version", 0),
     ("request_id", ""), ("payload", "{}"), ("payload", []),
     ("payload_json", "{}"), ("kind", "CloseLocation")],
)
def test_invalid_command_fields_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        CommandEnvelope.model_validate(COMMAND_EXAMPLE | {field: value})


def test_command_envelope_is_frozen() -> None:
    envelope = CommandEnvelope.model_validate(COMMAND_EXAMPLE)
    with pytest.raises(ValidationError):
        envelope.run_id = "run-other"
    with pytest.raises(TypeError):
        envelope.payload["reason"] = "changed"


def test_proposal_rejects_unknown_actions_and_source() -> None:
    proposal = {
        "agent_id": "agent-1", "action": "WAIT", "target": None,
        "source": "rule", "summary": "等待活动通知", "memory_refs": [],
    }
    assert ActionProposal.model_validate(proposal).memory_refs == ()
    for field, value in [("action", "TELEPORT"), ("source", "untracked"), ("summary", 5)]:
        with pytest.raises(ValidationError):
            ActionProposal.model_validate(proposal | {field: value})


def test_concrete_command_only_forwards_to_typed_receiver() -> None:
    class Receiver:
        def close_location(self, command: CloseLocationCommand) -> tuple[EventDraft, ...]:
            self.received = command
            return ()

    command = CloseLocationCommand(
        command_id="cmd-007", run_id="run-001", location_id="activity-room", reason="维护",
    )
    receiver = Receiver()
    assert command.execute(receiver) == ()
    assert receiver.received is command
    assert command.kind is CommandKind.CLOSE_LOCATION
    assert get_type_hints(World.close_location, localns=vars(commands))["command"] is CloseLocationCommand


def test_contract_imports_and_original_run_status_values() -> None:
    modules = [
        "app.domain.commands", "app.domain.events", "app.domain.world",
        "app.domain.run_states", "app.domain.strategies", "app.domain.memento",
        "app.ports.repositories", "app.ports.model_gateway", "app.cognition.observers",
        "app.cognition.llm_strategy", "app.application.command_processor",
        "app.application.decision_service", "app.application.replay_service",
        "app.application.simulation_facade",
    ]
    for module in modules:
        importlib.import_module(module)
    assert {item.value for item in RunStatus} == {
        "DRAFT", "READY", "RUNNING", "PAUSED", "FINISHED", "FAILED",
    }


def test_replay_returns_only_read_capabilities() -> None:
    from app.application.replay_service import ReplayService

    assert get_type_hints(ReplayService.state_at)["return"] is ReadOnlyView
    public_members = {
        name: member for name, member in vars(ReadOnlyView).items() if not name.startswith("_")
    }
    assert set(public_members) == {"run_id", "seq", "sim_time_ms", "snapshot"}
    assert all(isinstance(member, property) and member.fset is None for member in public_members.values())
    assert get_type_hints(ReadOnlyView.snapshot.fget)["return"] is WorldMemento
    assert not any(hasattr(ReadOnlyView, name) for name in ("apply_event", "execute", "submit"))


def test_event_hub_subscriptions_use_event_whitelist() -> None:
    from app.infrastructure.redis.transport import EventHub

    assert get_type_hints(EventHub.subscribe)["kind"] is EventType
    assert get_type_hints(EventHub.unsubscribe)["kind"] is EventType


def test_domain_has_no_infrastructure_imports() -> None:
    forbidden = {"sqlalchemy", "fastapi", "redis", "asyncpg", "openai", "anthropic"}
    domain_dir = Path(__file__).parents[1] / "app" / "domain"
    for path in domain_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [name.name for name in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported = [node.module or ""]
            else:
                continue
            assert all(name.split(".")[0] not in forbidden for name in imported), path.name
            assert all(not name.startswith("app.infrastructure") for name in imported), path.name
