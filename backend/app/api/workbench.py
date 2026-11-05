"""HTTP/WS transport only: Facade writes, read service queries, no ORM here."""
from uuid import uuid4

from fastapi import APIRouter, Depends, Path, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import Field
from typing import Annotated

from app.application.simulation_facade import SimulationFacade
from app.application.workbench import AgentDetail, EventPage, RunSummary, RunView, WorkbenchQueries
from app.domain.commands import CommandEnvelope, CommandKind, CommandReceipt
from app.domain.contract_types import ContractModel, FrozenJsonObject, Identifier, PositiveInt

router = APIRouter(tags=["workbench"])
RunID = Annotated[str, Path(min_length=1, max_length=128)]


class CommandSubmission(ContractModel):
    request_id: Annotated[Identifier, Field(max_length=128)]
    type: CommandKind
    schema_version: PositiveInt = 1
    payload: FrozenJsonObject


class RunList(ContractModel):
    items: tuple[RunSummary, ...]


def facade(request: Request) -> SimulationFacade:
    from app.bootstrap import build_facade
    return build_facade(request.app.state.resources)


def queries(request: Request) -> WorkbenchQueries:
    from app.bootstrap import build_queries
    return build_queries(request.app.state.resources)


@router.get("/runs", response_model=RunList)
async def list_runs(reads: Annotated[WorkbenchQueries, Depends(queries)]) -> RunList:
    return RunList(items=await reads.list_runs())


@router.get("/runs/{run_id}/state", response_model=RunView)
async def state(run_id: RunID, reads: Annotated[WorkbenchQueries, Depends(queries)]) -> RunView:
    return await reads.state(run_id)


@router.post("/runs/{run_id}/commands", response_model=CommandReceipt, status_code=202)
async def submit(run_id: RunID, body: CommandSubmission, service: Annotated[SimulationFacade, Depends(facade)]) -> CommandReceipt:
    envelope = CommandEnvelope(
        command_id=f"cmd-{uuid4().hex}", request_id=body.request_id,
        run_id=run_id, type=body.type, schema_version=body.schema_version, payload=body.payload,
    )
    return await service.submit(envelope)


@router.get("/runs/{run_id}/commands/{command_id}", response_model=CommandReceipt)
async def receipt(run_id: RunID, command_id: Annotated[str, Path(min_length=1, max_length=128)],
                  reads: Annotated[WorkbenchQueries, Depends(queries)]) -> CommandReceipt:
    return await reads.receipt(run_id, command_id)


@router.get("/runs/{run_id}/events", response_model=EventPage)
async def events(run_id: RunID, reads: Annotated[WorkbenchQueries, Depends(queries)],
                 after_seq: Annotated[int, Query(ge=0)] = 0,
                 limit: Annotated[int, Query(ge=1, le=200)] = 100) -> EventPage:
    return await reads.events(run_id, after_seq, limit)


@router.get("/runs/{run_id}/agents/{agent_id}", response_model=AgentDetail)
async def agent(run_id: RunID, agent_id: Annotated[str, Path(min_length=1, max_length=128)],
                reads: Annotated[WorkbenchQueries, Depends(queries)]) -> AgentDetail:
    return await reads.agent(run_id, agent_id)


@router.websocket("/runs/{run_id}/updates")
async def updates(websocket: WebSocket, run_id: str) -> None:
    # Browser /ws prefix is stripped by the existing Vite/Nginx proxy.
    from app.bootstrap import build_queries
    from app.infrastructure.postgres.repositories import RunNotFound
    try:
        await build_queries(websocket.app.state.resources).state(run_id)
    except RunNotFound:
        await websocket.close(code=1008, reason="run not found")
        return
    manager = websocket.app.state.connections
    await manager.connect(run_id, websocket)
    try:
        while True:
            # Client messages are only keepalives, never world commands.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(run_id, websocket)
