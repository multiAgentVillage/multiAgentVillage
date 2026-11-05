"""v2设计参考：可导入的接口/小例子，不是仿真应用或生产实现。

仅使用标准库。未实现数据库事务、任务领取、SDK、Schema解析和领域规则。
Python Protocol是静态契约；HTTP/消息输入仍需Pydantic运行时校验。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Protocol


class CommandKind(str, Enum):
    VALIDATE_CONFIG = "ValidateConfig"
    START = "StartRun"
    PAUSE = "PauseRun"
    RESUME = "ResumeRun"
    STOP = "StopRun"
    PUBLISH_NOTICE = "PublishNotice"
    CLOSE_LOCATION = "CloseLocation"
    PROPOSE_ACTION = "ProposeAction"
    COMPLETE_ACTION = "CompleteAction"


class Disposition(str, Enum):
    EXECUTE = "execute"
    DEFER = "defer"
    REJECT = "reject"


@dataclass(frozen=True)
class CommandEnvelope:
    command_id: str
    request_id: str
    run_id: str
    kind: CommandKind
    schema_version: int
    payload_json: str  # 不变JSON文本；生产中按白名单版本校验解码


@dataclass(frozen=True)
class CommandReceipt:
    command_id: str
    status: str  # accepted/applied/rejected等，accepted不等于世界已生效


@dataclass(frozen=True)
class EventDraft:
    """World产生的待提交事件；尚未分配全局信封和run内seq。"""
    kind: str
    payload_json: str


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    run_id: str
    seq: int
    kind: str
    payload_json: str


@dataclass(frozen=True)
class ActionProposal:
    agent_id: str
    action: str
    target: str | None
    source: str
    summary: str
    memory_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisionContext:
    run_id: str
    agent_id: str
    run_epoch: int
    agent_plan_version: int
    visible_facts: tuple[str, ...]
    model_allowed: bool  # 预算必须先在持久化任务层预留，并发下不能仅检查bool


class RunState(Protocol):
    """State角色：实例化状态行为；数据库仅保存状态码。"""
    def classify(self, kind: CommandKind) -> Disposition: ...
    def transition(self, kind: CommandKind) -> str: ...
    def can_advance(self) -> bool: ...


class RunningState:
    def classify(self, kind: CommandKind) -> Disposition:
        if kind in {CommandKind.VALIDATE_CONFIG, CommandKind.START, CommandKind.RESUME}:
            return Disposition.REJECT
        return Disposition.EXECUTE

    def transition(self, kind: CommandKind) -> str:
        if self.classify(kind) == Disposition.REJECT:
            raise ValueError("当前状态不允许该控制操作")
        if kind == CommandKind.PAUSE:
            return "PAUSED"
        if kind == CommandKind.STOP:
            return "FINISHED"
        return "RUNNING"

    def can_advance(self) -> bool:
        return True


class PausedState:
    def classify(self, kind: CommandKind) -> Disposition:
        if kind in {CommandKind.RESUME, CommandKind.STOP}:
            return Disposition.EXECUTE
        if kind in {CommandKind.PROPOSE_ACTION, CommandKind.COMPLETE_ACTION}:
            return Disposition.DEFER
        return Disposition.REJECT

    def transition(self, kind: CommandKind) -> str:
        if kind == CommandKind.RESUME:
            return "RUNNING"
        if kind == CommandKind.STOP:
            return "FINISHED"
        raise ValueError("暂停期间不执行新的世界动作")

    def can_advance(self) -> bool:
        return False


class WorldReceiver(Protocol):
    """World的最小Receiver接口。实现必须自行检查全部世界约束。"""
    def propose_action(self, command: ProposeActionCommand) -> tuple[EventDraft, ...]: ...
    def close_location(self, command: CloseLocationCommand) -> tuple[EventDraft, ...]: ...


class WorldCommand(Protocol):
    @property
    def command_id(self) -> str: ...
    @property
    def run_id(self) -> str: ...
    @property
    def kind(self) -> CommandKind: ...
    def execute(self, world: WorldReceiver) -> tuple[EventDraft, ...]: ...


@dataclass(frozen=True)
class ProposeActionCommand:
    command_id: str
    run_id: str
    run_epoch: int
    agent_plan_version: int
    resource_revisions: tuple[tuple[str, int], ...]
    proposal: ActionProposal

    @property
    def kind(self) -> CommandKind:
        return CommandKind.PROPOSE_ACTION

    def execute(self, world: WorldReceiver) -> tuple[EventDraft, ...]:
        return world.propose_action(self)


@dataclass(frozen=True)
class CloseLocationCommand:
    command_id: str
    run_id: str
    location_id: str
    reason: str

    @property
    def kind(self) -> CommandKind:
        return CommandKind.CLOSE_LOCATION

    def execute(self, world: WorldReceiver) -> tuple[EventDraft, ...]:
        return world.close_location(self)


class EventObserver(Protocol):
    observer_id: str
    async def on_event(self, event: DomainEvent) -> None: ...


class EventHub:
    """本地Observer Subject。跨进程传输、消费事务、ACK另行实现。"""
    def __init__(self) -> None:
        self._observers: dict[str, dict[str, EventObserver]] = {}

    def subscribe(self, kind: str, observer: EventObserver) -> None:
        self._observers.setdefault(kind, {})[observer.observer_id] = observer

    def unsubscribe(self, kind: str, observer_id: str) -> None:
        self._observers.get(kind, {}).pop(observer_id, None)

    async def notify(self, event: DomainEvent) -> None:
        for observer in tuple(self._observers.get(event.kind, {}).values()):
            # 每个observer内部落实自身事务与去重；失败传播，外层不得提前ACK。
            await observer.on_event(event)


class ModelUnavailable(Exception):
    """Adapter转换后的可降级错误，不能用它隐藏任意编程异常。"""


class InvalidModelOutput(Exception):
    """由策略中的Schema解析产生的可降级格式错误。"""


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    max_output_tokens: int


@dataclass(frozen=True)
class ModelResponse:
    text: str
    input_tokens: int | None
    output_tokens: int | None


class ModelGateway(Protocol):
    """Adapter Target；ProviderAdapter在infrastructure/providers中实现。"""
    async def generate(self, request: ModelRequest) -> ModelResponse: ...


class DecisionStrategy(Protocol):
    async def decide(self, context: DecisionContext) -> ActionProposal: ...


class RuleDecisionStrategy:
    async def decide(self, context: DecisionContext) -> ActionProposal:
        return ActionProposal(context.agent_id, "WAIT", None, "rule", "暂时等待")


class LLMDecisionStrategy:
    def __init__(
        self,
        gateway: ModelGateway,
        build_request: Callable[[DecisionContext], ModelRequest],
        parse_proposal: Callable[[ModelResponse, DecisionContext], ActionProposal],
    ) -> None:
        self.gateway = gateway
        self.build_request = build_request
        self.parse_proposal = parse_proposal

    async def decide(self, context: DecisionContext) -> ActionProposal:
        response = await self.gateway.generate(self.build_request(context))
        return self.parse_proposal(response, context)


class DecisionService:
    """Strategy Context；生产实现还需任务状态、预算、版本及结果持久化。"""
    def __init__(self, preferred: DecisionStrategy, fallback: DecisionStrategy) -> None:
        self.preferred = preferred
        self.fallback = fallback

    async def decide(self, context: DecisionContext) -> ActionProposal:
        if not context.model_allowed:
            return await self.fallback.decide(context)
        try:
            return await self.preferred.decide(context)
        except (ModelUnavailable, InvalidModelOutput):
            # 生产中同时记录降级原因/用量；不吞数据库异常或代码错误。
            return await self.fallback.decide(context)


class CommandInbox(Protocol):
    async def append(self, envelope: CommandEnvelope) -> CommandReceipt: ...


class SimulationFacade:
    """Facade的提交部分；查询与回放在生产中组合Read/ReplayService。"""
    def __init__(self, inbox: CommandInbox) -> None:
        self.inbox = inbox

    async def submit(self, envelope: CommandEnvelope) -> CommandReceipt:
        return await self.inbox.append(envelope)


@dataclass(frozen=True)
class WorldMemento:
    run_id: str
    seq: int
    sim_time_ms: int
    schema_version: int
    state_hash: str
    _opaque_state_json: str  # 只由World解释；Caretaker不修改领域字段


class SnapshotStore(Protocol):
    async def save(self, memento: WorldMemento) -> None: ...
    async def load_nearest(self, run_id: str, seq: int) -> WorldMemento: ...


class World(WorldReceiver, Protocol):
    """Originator的快照接口；生产类同时承担U03中的Receiver职责。"""
    def create_memento(self) -> WorldMemento: ...
    @classmethod
    def from_memento(cls, memento: WorldMemento, *, read_only: bool) -> World: ...
    def apply_event(self, event: DomainEvent) -> None: ...


# 注册表只用于组装，不是GoF Factory Method；不从请求动态导入类型。
CommandDecoder = Callable[[CommandEnvelope], WorldCommand]


class CommandCodec:
    def __init__(self, decoders: Mapping[tuple[CommandKind, int], CommandDecoder]) -> None:
        self._decoders = dict(decoders)

    def decode(self, envelope: CommandEnvelope) -> WorldCommand:
        decoder = self._decoders[(envelope.kind, envelope.schema_version)]
        return decoder(envelope)
