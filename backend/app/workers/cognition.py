"""Cognition entry point: observation only, with no model or decision loop."""
import asyncio

from app.workers.base import run_process
from app.workers.consumers import run_cognition


async def main() -> None:
    await run_process("cognition", (run_cognition,))


if __name__ == "__main__":
    asyncio.run(main())
