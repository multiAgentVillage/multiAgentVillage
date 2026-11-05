"""ASGI entry point and the display consumer group, one API process for W1."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import router
from app.api.workbench import router as workbench_router
from app.bootstrap import build_resources
from app.config import Settings


def create_app(settings: Settings | None = None, *, start_consumers: bool = True) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        resources = build_resources(settings)
        app.state.resources = resources
        from app.infrastructure.realtime import ConnectionManager
        app.state.connections = ConnectionManager()
        stop = asyncio.Event()
        consumer_task = None
        if start_consumers:
            from app.workers.consumers import run_display
            consumer_task = asyncio.create_task(run_display(resources, app.state.connections, stop))
        try:
            yield
        finally:
            stop.set()
            if consumer_task:
                try:
                    await asyncio.wait_for(consumer_task, timeout=10)
                except TimeoutError:
                    consumer_task.cancel()
                    await asyncio.gather(consumer_task, return_exceptions=True)
            await resources.close()

    app = FastAPI(
        title="Campus Emergence API", version="0.3.0",
        description="W1 PublishNotice walking skeleton. Commands are accepted before they take effect.",
        lifespan=lifespan,
    )
    app.include_router(router)
    app.include_router(workbench_router)

    from app.infrastructure.postgres.repositories import RequestConflict, RunNotFound
    from app.infrastructure.postgres.workbench import ResourceNotFound

    @app.exception_handler(RequestConflict)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": "同一请求标识已对应不同内容，请使用新的请求标识"})

    @app.exception_handler(RunNotFound)
    @app.exception_handler(ResourceNotFound)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": "请求的运行、命令或角色不存在"})

    @app.exception_handler(SQLAlchemyError)
    async def database_unavailable(request, exc):
        logging.getLogger(__name__).warning("database operation failed", exc_info=True)
        return JSONResponse(status_code=503, content={"detail": "数据库暂时不可用，请保留原请求后重试"})
    return app


app = create_app()
