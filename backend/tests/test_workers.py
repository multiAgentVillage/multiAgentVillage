"""Idle lifecycle must respond promptly to shutdown, without doing business work."""
import asyncio

from app.workers.base import idle_loop, repeat


async def test_idle_loop_exits_when_stopped():
    stop = asyncio.Event()
    task = asyncio.create_task(idle_loop("test", stop, interval=60))
    await asyncio.sleep(0)
    stop.set()
    await asyncio.wait_for(task, timeout=1)


async def test_retry_loop_continues_after_temporary_failure():
    stop = asyncio.Event()
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("temporary dependency outage")
        stop.set()

    await asyncio.wait_for(repeat("test", stop, 0.001, operation), timeout=1)
    assert calls == 2
