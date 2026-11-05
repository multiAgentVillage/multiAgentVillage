"""Composition root: concrete infrastructure is assembled behind application ports."""
import asyncio
import logging
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class Resources:
    settings: Settings
    engine: AsyncEngine
    redis: Redis

    @property
    def sessions(self) -> async_sessionmaker:
        return async_sessionmaker(self.engine, expire_on_commit=False)

    async def readiness(self) -> dict[str, str]:
        async def postgres_check() -> str:
            try:
                async with asyncio.timeout(self.settings.health_timeout_seconds):
                    async with self.engine.connect() as connection:
                        await connection.execute(text("SELECT 1"))
                return "ok"
            except Exception:
                logger.warning("postgres readiness check failed")
                return "unavailable"

        async def redis_check() -> str:
            try:
                async with asyncio.timeout(self.settings.health_timeout_seconds):
                    await self.redis.ping()
                return "ok"
            except Exception:
                logger.warning("redis readiness check failed")
                return "unavailable"

        postgres_status, redis_status = await asyncio.gather(postgres_check(), redis_check())
        return {"postgres": postgres_status, "redis": redis_status}

    async def close(self) -> None:
        try:
            await self.redis.aclose()
        finally:
            await self.engine.dispose()


def build_resources(settings: Settings) -> Resources:
    engine = create_async_engine(settings.sqlalchemy_url, pool_pre_ping=True)
    redis = Redis.from_url(
        settings.redis_url.get_secret_value(), decode_responses=True,
        socket_connect_timeout=settings.health_timeout_seconds,
        socket_timeout=settings.health_timeout_seconds,
    )
    return Resources(settings=settings, engine=engine, redis=redis)


def build_facade(resources: Resources):
    from app.application.simulation_facade import SimulationFacade
    from app.infrastructure.postgres.repositories import PostgresCommandInbox, PostgresReadService
    return SimulationFacade(
        PostgresCommandInbox(resources.sessions), PostgresReadService(resources.sessions), None,
    )


def build_queries(resources: Resources):
    from app.infrastructure.postgres.workbench import PostgresWorkbenchQueries
    return PostgresWorkbenchQueries(resources.sessions)


def build_processor(resources: Resources):
    from app.application.command_processor import CommandProcessor
    from app.infrastructure.postgres.repositories import PostgresUnitOfWork, PublishNoticeCodec
    return CommandProcessor(lambda: PostgresUnitOfWork(resources.sessions), PublishNoticeCodec())
