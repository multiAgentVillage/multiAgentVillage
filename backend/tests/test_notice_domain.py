"""Business behavior of the PublishNotice Command/State slice, without I/O."""
import pytest

from app.domain.campus_world import CampusWorld, NoticeRunState
from app.domain.commands import CommandEnvelope, CommandKind, PublishNoticeCommand
from app.domain.errors import CommandDecodeError, CommandRejected
from app.domain.events import EventType
from app.domain.run_states import Disposition, RunStatus
from app.infrastructure.postgres.repositories import PublishNoticeCodec


def world(status: RunStatus = RunStatus.RUNNING) -> CampusWorld:
    return CampusWorld(
        run_id="test-run", status=status, sim_time_ms=500, run_epoch=0,
        last_seq=2, agent_ids=tuple(f"agent-{number}" for number in range(8)),
    )


def command(**changes) -> PublishNoticeCommand:
    return PublishNoticeCommand.model_validate({
        "command_id": "test-command", "run_id": "test-run", "content": "读书会今晚开始",
        **changes,
    })


def test_broadcast_freezes_recipients_and_causation_at_execution():
    current = world()
    (event,) = command().execute(current)
    assert event.type is EventType.NOTICE_PUBLISHED
    assert event.payload["recipient_agent_ids"] == current.agent_ids
    assert event.payload["content"] == "读书会今晚开始"
    assert event.causation_id == event.correlation_id == "test-command"
    assert event.sim_time_ms == 500 and event.occurred_at.utcoffset() is not None
    assert current.last_seq == 2  # Invoker's EventStore assigns the next seq.


def test_targeted_notice_normalizes_duplicate_recipients_to_roster_order():
    (event,) = command(recipient_agent_ids=["agent-7", "agent-1", "agent-1"]).execute(world())
    assert event.payload["recipient_agent_ids"] == ("agent-1", "agent-7")


@pytest.mark.parametrize("changes", [
    {"run_id": "another-run"}, {"content": "  \n"}, {"content": "x" * 2001},
    {"recipient_agent_ids": ["unknown-agent"]},
])
def test_invalid_notice_produces_no_domain_event(changes):
    current = world()
    with pytest.raises(CommandRejected):
        command(**changes).execute(current)
    assert current.last_seq == 2


@pytest.mark.parametrize(("status", "disposition"), [
    (RunStatus.DRAFT, Disposition.REJECT), (RunStatus.READY, Disposition.REJECT),
    (RunStatus.RUNNING, Disposition.EXECUTE), (RunStatus.PAUSED, Disposition.REJECT),
    (RunStatus.FINISHED, Disposition.REJECT), (RunStatus.FAILED, Disposition.REJECT),
])
def test_state_authorization_does_not_implement_lifecycle(status, disposition):
    state = NoticeRunState(status)
    assert state.classify(CommandKind.PUBLISH_NOTICE) is disposition
    assert state.classify(CommandKind.START) is Disposition.REJECT
    assert state.transition(CommandKind.PUBLISH_NOTICE) is status


def test_paused_notice_is_rejected_before_an_event_is_created():
    current = world(RunStatus.PAUSED)
    with pytest.raises(CommandRejected, match="PAUSED"):
        command().execute(current)
    assert current.last_seq == 2


def test_codec_decodes_data_without_executing_world():
    envelope = CommandEnvelope(
        command_id="command-1", request_id="request-1", run_id="test-run",
        type="PublishNotice", payload={"content": "活动通知"},
    )
    decoded = PublishNoticeCodec().decode(envelope)
    assert decoded.command_id == envelope.command_id and decoded.content == "活动通知"


@pytest.mark.parametrize("changes", [
    {"schema_version": 2}, {"type": "PauseRun"}, {"payload": {}},
    {"payload": {"content": 1}}, {"payload": {"content": "通知", "run_id": "injected-run"}},
    {"payload": {"content": "通知", "command_id": "injected-cause"}},
])
def test_codec_rejects_unsupported_or_invalid_persisted_commands(changes):
    values = {
        "command_id": "command-1", "request_id": "request-1", "run_id": "test-run",
        "type": "PublishNotice", "payload": {"content": "活动通知"}, **changes,
    }
    with pytest.raises(CommandDecodeError):
        PublishNoticeCodec().decode(CommandEnvelope.model_validate(values))
