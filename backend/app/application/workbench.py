"""Read DTOs and query port for the W1 workbench; no storage dependency."""
from typing import Protocol

from app.domain.commands import CommandReceipt
from app.domain.contract_types import ContractModel, Identifier, NonNegativeInt
from app.domain.events import DomainEvent
from app.domain.run_states import RunStatus


class RunSummary(ContractModel):
    run_id: Identifier
    name: str
    status: RunStatus
    sim_time_ms: NonNegativeInt
    last_seq: NonNegativeInt


class LocationView(ContractModel):
    location_id: Identifier
    name: str
    is_open: bool


class AgentView(ContractModel):
    agent_id: Identifier
    name: str
    location_id: str | None
    location_name: str | None


class RunView(RunSummary):
    locations: tuple[LocationView, ...]
    agents: tuple[AgentView, ...]


class MemoryView(ContractModel):
    memory_id: Identifier
    source_event_id: Identifier
    content: str
    sim_time_ms: NonNegativeInt


class AgentDetail(AgentView):
    memories: tuple[MemoryView, ...]


class EventPage(ContractModel):
    items: tuple[DomainEvent, ...]
    next_seq: NonNegativeInt
    has_more: bool


class WorkbenchQueries(Protocol):
    async def list_runs(self) -> tuple[RunSummary, ...]: ...
    async def state(self, run_id: str) -> RunView: ...
    async def events(self, run_id: str, after_seq: int, limit: int) -> EventPage: ...
    async def receipt(self, run_id: str, command_id: str) -> CommandReceipt: ...
    async def agent(self, run_id: str, agent_id: str) -> AgentDetail: ...
