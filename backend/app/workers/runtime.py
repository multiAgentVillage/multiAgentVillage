"""Runtime entry point: owns Scheduler/CommandProcessor and OutboxDispatcher loops."""
import asyncio

from sqlalchemy import select

from app.bootstrap import Resources, build_processor
from app.infrastructure.postgres.models import CommandRecord
from app.workers.base import repeat, run_process
from app.workers.outbox import run as outbox_loop


async def scheduler_loop(resources: Resources, stop: asyncio.Event) -> None:
    processor = build_processor(resources)

    async def process_pending() -> None:
        # Discover runs without claiming inputs; the processor serializes each run.
        async with resources.sessions() as session:
            run_ids = (await session.scalars(select(CommandRecord.run_id).where(
                CommandRecord.status == "pending",
            ).distinct().order_by(CommandRecord.run_id).limit(100))).all()
        for run_id in run_ids:
            if stop.is_set():
                break
            await processor.process_next(run_id)

    await repeat("CommandProcessor", stop, resources.settings.worker_poll_interval_seconds, process_pending)


async def main() -> None:
    await run_process("runtime", (scheduler_loop, outbox_loop))


if __name__ == "__main__":
    asyncio.run(main())
