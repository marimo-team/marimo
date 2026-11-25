# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from marimo._utils.async_map import bounded_map


async def test_bounds_tasks_and_preserves_order():
    release = asyncio.Event()
    started = asyncio.Event()
    later_finished = asyncio.Event()
    active = 0
    peak = 0

    async def work(value: int) -> int | None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 3:
            started.set()
        await release.wait()
        if value == 0:
            await later_finished.wait()
        elif value == 2:
            later_finished.set()
        await asyncio.sleep(0)
        active -= 1
        return value if value else None

    with patch("asyncio.create_task", wraps=asyncio.create_task) as create:
        task = asyncio.create_task(
            bounded_map(work, list(range(1000)), concurrency=3)
        )
        await started.wait()
        assert create.call_count == 4  # Parent plus three workers.
        assert peak == 3
        release.set()
        assert await task == [None, *range(1, 1000)]


@pytest.mark.parametrize("cancel", [False, True])
async def test_failure_and_cancellation_drain_workers(cancel: bool):
    started = asyncio.Event()
    release = asyncio.Event()
    cleaned: set[int] = set()

    async def work(value: int) -> int:
        try:
            if value == 1:
                started.set()
            await release.wait()
            if value == 0:
                raise ValueError("failed")
            await asyncio.Event().wait()
            return value
        finally:
            cleaned.add(value)

    task = asyncio.create_task(bounded_map(work, [0, 1, 2], concurrency=2))
    await started.wait()
    if cancel:
        task.cancel()
    else:
        release.set()
    with pytest.raises(asyncio.CancelledError if cancel else ValueError):
        await task
    assert cleaned == {0, 1}


async def test_empty_and_invalid_concurrency():
    async def work(value: int) -> int:
        raise AssertionError(value)

    assert await bounded_map(work, [], concurrency=2) == []
    with pytest.raises(ValueError, match="positive"):
        await bounded_map(work, [], concurrency=0)
