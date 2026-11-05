"""Shared startup, retry loops and graceful shutdown for the three process roles."""
import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable

from app.bootstrap import Resources, build_resources
from app.config import Settings

logger = logging.getLogger(__name__)
Loop = Callable[[Resources, asyncio.Event], Awaitable[None]]


async def idle_loop(name: str, stop: asyncio.Event, interval: float) -> None:
    logger.info("%s is idle: business processing is not implemented", name)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass


async def repeat(
    name: str, stop: asyncio.Event, interval: float, operation: Callable[[], Awaitable[object]],
) -> None:
    """Retry temporary dependency failures; never acknowledge on an exception."""
    while not stop.is_set():
        try:
            await operation()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("%s failed; durable work will be retried", name)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass


async def run_process(name: str, loops: tuple[Loop, ...]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    resources = build_resources(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous_handlers: dict[signal.Signals, object] = {}
    installed: list[signal.Signals] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[sig] = signal.getsignal(sig)
        try:
            loop.add_signal_handler(sig, stop.set)
            installed.append(sig)
        except NotImplementedError:  # Windows local development
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    try:
        dependencies = await resources.readiness()
        if any(status != "ok" for status in dependencies.values()):
            raise RuntimeError(f"{name} infrastructure is unavailable: {dependencies}")
        logger.info("%s started: PublishNotice W1 slice", name)
        async with asyncio.TaskGroup() as tasks:
            for worker_loop in loops:
                tasks.create_task(worker_loop(resources, stop))
    finally:
        stop.set()
        for sig in installed:
            loop.remove_signal_handler(sig)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
        await resources.close()
        logger.info("%s stopped", name)
