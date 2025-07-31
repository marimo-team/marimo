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
