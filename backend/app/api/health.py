"""Liveness and real PostgreSQL/Redis readiness checks."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    dependencies = await request.app.state.resources.readiness()
    available = all(value == "ok" for value in dependencies.values())
    return JSONResponse(
        status_code=200 if available else 503,
        content={"status": "ready" if available else "not_ready", "dependencies": dependencies},
    )
