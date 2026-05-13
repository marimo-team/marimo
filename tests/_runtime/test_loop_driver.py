# Copyright 2026 Marimo. All rights reserved.
"""End-to-end tests for `LoopDriver` driving a real kernel."""

from __future__ import annotations

import asyncio
from typing import Any

from marimo._runtime.commands import ExecuteCellsCommand, StopKernelCommand
from marimo._types.ids import CellId_t
from tests._runtime._helpers import LoopDriver, mocked_kernel_session


def _exec(*pairs: tuple[str, str]) -> ExecuteCellsCommand:
    """Build an ExecuteCellsCommand from (cell_id, code) pairs."""
    return ExecuteCellsCommand(
        cell_ids=[CellId_t(cid) for cid, _ in pairs],
        codes=[code for _, code in pairs],
    )


async def test_loop_driver_runs_command_through_real_kernel() -> None:
    """Enqueueing a command drives the kernel's full pipeline."""
    with mocked_kernel_session() as tk:
        control: asyncio.Queue[Any] = asyncio.Queue()
        ui: asyncio.Queue[Any] = asyncio.Queue()
        driver = LoopDriver(tk.kernel, control, ui)
        await driver.start()

        driver.enqueue(_exec(("c0", "x = 42")))
        await driver.settle()
        await driver.stop()

        assert tk.kernel.globals["x"] == 42


async def test_loop_driver_stops_on_stop_command() -> None:
    with mocked_kernel_session() as tk:
        control: asyncio.Queue[Any] = asyncio.Queue()
        ui: asyncio.Queue[Any] = asyncio.Queue()
        driver = LoopDriver(tk.kernel, control, ui)
        await driver.start()
        await driver.stop()  # also calls listener task; awaits exit


async def test_loop_driver_preserves_request_order() -> None:
    """Multiple batched commands run in enqueue order."""
    with mocked_kernel_session() as tk:
        control: asyncio.Queue[Any] = asyncio.Queue()
        ui: asyncio.Queue[Any] = asyncio.Queue()
        driver = LoopDriver(tk.kernel, control, ui)
        await driver.start()

        driver.enqueue(
            _exec(("c1", "a = 1")),
            _exec(("c2", "b = a + 1")),
            _exec(("c3", "c = b + 1")),
        )
        await driver.settle()
        await driver.stop()

        assert tk.kernel.globals["a"] == 1
        assert tk.kernel.globals["b"] == 2
        assert tk.kernel.globals["c"] == 3


async def test_loop_driver_drains_stop_before_pending() -> None:
    """StopKernelCommand short-circuits the loop even with requests behind it."""
    with mocked_kernel_session() as tk:
        control: asyncio.Queue[Any] = asyncio.Queue()
        ui: asyncio.Queue[Any] = asyncio.Queue()
        driver = LoopDriver(tk.kernel, control, ui)
        await driver.start()

        driver.enqueue(_exec(("c1", "first = 1")))
        # Stop is enqueued before the second exec; the second must not run.
        control.put_nowait(StopKernelCommand())
        driver.enqueue(_exec(("c2", "second = 2")))

        await driver.stop()
        assert tk.kernel.globals["first"] == 1
        assert "second" not in tk.kernel.globals
