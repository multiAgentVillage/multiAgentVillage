"""Run with python -m app.seed [--run-id ID] after Alembic upgrade head."""
import argparse
import asyncio
import json

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.demo import DEFAULT_RUN_ID
from app.config import Settings
from app.infrastructure.postgres.demo import initialize_demo


async def seed(run_id: str) -> None:
    engine = create_async_engine(Settings().sqlalchemy_url)
    try:
        created = await initialize_demo(async_sessionmaker(engine, expire_on_commit=False), run_id)
        print(json.dumps({"run_id": run_id, "created": created}, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an insert-only W1 demo run")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    asyncio.run(seed(parser.parse_args().run_id))
