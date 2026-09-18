# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import signal
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import ExecutionContext
from marimo._runtime.control_flow import MarimoInterrupt
from marimo._runtime.handlers import construct_interrupt_handler
from marimo._runtime.interrupts import InterruptScope

if TYPE_CHECKING:
    from collections.abc import Iterator

HAS_DUCKDB = DependencyManager.duckdb.has()


@contextmanager
def _kernel_context(exec_ctx: ExecutionContext | None) -> Iterator[MagicMock]:
    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = exec_ctx
    ctx.interrupt_scope = None
    ctx.stream = MagicMock()
    with (
        patch("marimo._runtime.handlers.safe_get_context", return_value=ctx),
        patch("marimo._runtime.interrupts.safe_get_context", return_value=ctx),
    ):
        yield ctx


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
async def test_duckdb_interrupt_handler_called_when_connection_present():
    import duckdb

    mock_conn = MagicMock(spec=duckdb.DuckDBPyConnection)
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)
    with (
        _kernel_context(exec_ctx),
        InterruptScope() as interrupts,
        exec_ctx.with_connection(mock_conn),
    ):
        with pytest.raises(MarimoInterrupt), interrupts.guard():
            construct_interrupt_handler()(signal.SIGINT, None)
        mock_conn.interrupt.assert_called_once()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
async def test_duckdb_interrupt_handler_exception_handling():
    import duckdb

    mock_conn = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_conn.interrupt.side_effect = RuntimeError("Mock error")
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)
    with (
        _kernel_context(exec_ctx),
        InterruptScope() as interrupts,
        exec_ctx.with_connection(mock_conn),
    ):
        with pytest.raises(MarimoInterrupt), interrupts.guard():
            construct_interrupt_handler()(signal.SIGINT, None)
        mock_conn.interrupt.assert_called_once()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
async def test_duckdb_interrupt_handler_no_error_when_connection_none():
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)
    with _kernel_context(exec_ctx), InterruptScope() as interrupts:
        with pytest.raises(MarimoInterrupt), interrupts.guard():
            construct_interrupt_handler()(signal.SIGINT, None)


async def test_sigint_between_cells_records_interruption_without_raising() -> (
    None
):
    with _kernel_context(None), InterruptScope() as interrupts:
        construct_interrupt_handler()(signal.SIGINT, None)
        assert interrupts.interrupted


async def test_sigint_with_active_async_task_cancels_without_raising() -> None:
    started = asyncio.Event()

    async def work() -> None:
        started.set()
        await asyncio.sleep(60)

    async def interrupt_once_started() -> None:
        await started.wait()
        # The handler returns normally; the work is cancelled instead.
        construct_interrupt_handler()(signal.SIGINT, None)

    with _kernel_context(None), InterruptScope() as interrupts:
        firing = asyncio.create_task(interrupt_once_started())
        with pytest.raises(MarimoInterrupt):
            await interrupts.run(work())
        await firing
        assert interrupts.interrupted


def test_sigint_with_no_scheduler_and_no_cell_is_noop() -> None:
    with _kernel_context(None) as ctx:
        construct_interrupt_handler()(signal.SIGINT, None)
        ctx.stream.write.assert_not_called()


def test_ignore_console_ctrl_c_keeps_interrupt_main_working() -> None:
    """`interrupt_main()` (the deliberate interrupt path) must still fire
    the SIGINT handler after `ignore_console_ctrl_c()`. Runs in a
    subprocess to leave the test runner's console handling untouched."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        import signal, sys, threading, _thread
        from marimo._runtime.win32_interrupt_handler import (
            ignore_console_ctrl_c,
        )

        fired = threading.Event()
        signal.signal(signal.SIGINT, lambda *args: fired.set())
        ignore_console_ctrl_c()
        threading.Timer(0.1, _thread.interrupt_main).start()
        fired.wait(5)
        sys.exit(0 if fired.is_set() else 1)
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], timeout=30, capture_output=True
    )
    assert completed.returncode == 0, completed.stderr.decode()
