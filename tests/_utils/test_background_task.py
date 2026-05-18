from __future__ import annotations

import asyncio

import pytest

from marimo._utils.background_task import AsyncBackgroundTask


class SimpleTask(AsyncBackgroundTask):
    def __init__(self):
        super().__init__()
        self.startup_called = False
        self.run_called = False
        self.shutdown_called = False
        self.should_raise = False

    async def startup(self):
        self.startup_called = True

    async def run(self):
        self.run_called = True
        if self.should_raise:
            raise ValueError("Test error")
        while self.running:  # noqa: ASYNC110
            await asyncio.sleep(0.1)

    async def shutdown(self):
        self.shutdown_called = True


async def test_task_lifecycle():
    task = SimpleTask()

    # Test startup
    task.start()
    await task.wait_for_startup()
    assert task.startup_called
    assert task.running
    assert task.task is not None
    assert not task.task.done()

    # Test stop
    await task.stop()
    assert not task.running
    assert task.shutdown_called
    assert task.task.done()


async def test_context_manager():
    async with SimpleTask() as task:
        assert task.startup_called
        assert task.running
        assert task.task is not None
        assert not task.task.done()

    assert not task.running
    assert task.shutdown_called
    assert task.task.done()


async def test_error_handling():
    task = SimpleTask()
    task.should_raise = True

    task.start()
    with pytest.raises(ValueError, match="Test error"):
        await task.task

    assert not task.running
    assert task.shutdown_called


async def test_stop_timeout():
    task = SimpleTask()
    task.start()
    await task.wait_for_startup()

    # Test timeout
    await task.stop(timeout=0.1)
    assert not task.running
    assert task.task is not None
    assert task.task.done()


async def test_stop_sync():
    task = SimpleTask()

    async def run():
        task.start()

    await run()
    task.stop_sync(timeout=0.5)
    assert not task.running
    assert task.task is not None
    await asyncio.sleep(0)  # Wait a tick
    assert task.task.done(), "Task should be done"


def test_stop_sync_from_other_thread_drives_shutdown():
    """stop_sync called from a non-loop thread should block on the
    task's own loop and honor the timeout, instead of silently
    returning without ever stopping the task."""
    import threading

    bg_task = SimpleTask()
    loop_ready = threading.Event()
    loop_done = threading.Event()
    loop_holder: dict[str, asyncio.AbstractEventLoop] = {}

    def run_loop() -> None:
        loop = asyncio.new_event_loop()
        loop_holder["loop"] = loop
        asyncio.set_event_loop(loop)
        # ``start()`` calls ``asyncio.create_task`` which requires a
        # running loop, so schedule it on the loop itself.
        loop.call_soon(bg_task.start)
        loop.call_soon(loop_ready.set)
        try:
            loop.run_forever()
        finally:
            loop.close()
            loop_done.set()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    loop_ready.wait(timeout=2.0)

    # From the main thread, stop the task that's running on the
    # background-thread loop. This exercises the run_coroutine_threadsafe
    # path; without that, the timeout would be ignored and the task
    # would still be alive.
    bg_task.stop_sync(timeout=1.0)
    assert bg_task.task is not None
    assert bg_task.task.done()

    # Tear down the background loop.
    loop_holder["loop"].call_soon_threadsafe(loop_holder["loop"].stop)
    loop_done.wait(timeout=2.0)
