# Copyright 2026 Marimo. All rights reserved.
"""Tests for the control loop's event loop behavior.

The kernel control loop polls a synchronous queue for messages.
These tests verify that the polling strategy does not starve
background asyncio tasks.
"""

from __future__ import annotations

import asyncio
import queue
import time

import pytest


@pytest.mark.asyncio
async def test_executor_queue_get_does_not_starve_background_tasks():
    """run_in_executor keeps the event loop free for background tasks.

    This is the pattern used by the fixed control loop: the blocking
    queue.get() runs in a thread, so the event loop can service other
    tasks while waiting.
    """
    q: queue.Queue[None] = queue.Queue()
    loop = asyncio.get_running_loop()
    count = 0

    async def background():
        nonlocal count
        end = time.time() + 0.5
        while time.time() < end:
            count += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(background())

    # Simulate the NEW control loop: run_in_executor
    end = time.time() + 0.5
    while time.time() < end:
        try:
            await loop.run_in_executor(None, lambda: q.get(timeout=0.1))
        except queue.Empty:
            pass

    await task
    # With run_in_executor, the task runs freely: ~45 iterations in 0.5s.
    assert count > 30
