# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import ExecutionContext
from marimo._runtime.handlers import construct_interrupt_handler
from marimo._runtime.runtime import MarimoInterrupt

HAS_DUCKDB = DependencyManager.duckdb.has()


def _kernel_context_mock(exec_ctx: ExecutionContext) -> MagicMock:
    """Mock that satisfies the handler's `isinstance(KernelRuntimeContext)`
    check; `active_scheduler=None` selects the sync raise path."""
    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = exec_ctx
    ctx.active_scheduler = None
    return ctx


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_interrupt_handler_called_when_connection_present():
    """Test that duckdb.interrupt() is called when a connection is present."""
    import duckdb

    # Create a mock connection that we can spy on
    mock_conn = MagicMock(spec=duckdb.DuckDBPyConnection)

    # Create an execution context with a duckdb connection
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)

    with patch(
        "marimo._runtime.handlers.safe_get_context"
    ) as mock_safe_get_context:
        mock_safe_get_context.return_value = _kernel_context_mock(exec_ctx)

        with exec_ctx.with_connection(mock_conn):
            interrupt_handler = construct_interrupt_handler()

            # Trigger the interrupt handler
            with pytest.raises(MarimoInterrupt):
                interrupt_handler(signal.SIGINT, None)

            # Verify duckdb connection's interrupt was called
            mock_conn.interrupt.assert_called_once()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_interrupt_handler_no_error_when_connection_none():
    """Test that no error occurs when connection is None."""
    # Create an execution context without a connection
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)
    exec_ctx.duckdb_connection = None

    # Mock the context to return our execution context
    with patch(
        "marimo._runtime.handlers.safe_get_context"
    ) as mock_safe_get_context:
        mock_context = _kernel_context_mock(exec_ctx)
        mock_safe_get_context.return_value = mock_context

        interrupt_handler = construct_interrupt_handler()

        # Should not raise error from duckdb interrupt (only MarimoInterrupt)
        with pytest.raises(MarimoInterrupt):
            interrupt_handler(signal.SIGINT, None)


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_interrupt_handler_exception_handling():
    """Test that exceptions during interrupt() don't crash the kernel."""
    import duckdb

    # Create a mock connection that raises an exception
    mock_conn = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_conn.interrupt.side_effect = RuntimeError("Mock error")

    # Create an execution context with a duckdb connection
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)

    # Mock the context to return our execution context
    with patch(
        "marimo._runtime.handlers.safe_get_context"
    ) as mock_safe_get_context:
        mock_context = _kernel_context_mock(exec_ctx)
        mock_safe_get_context.return_value = mock_context

        # Make interrupt() raise an exception
        with exec_ctx.with_connection(mock_conn):
            interrupt_handler = construct_interrupt_handler()

            # Should raise MarimoInterrupt, not RuntimeError
            # The RuntimeError should be caught and logged
            with pytest.raises(MarimoInterrupt):
                interrupt_handler(signal.SIGINT, None)

            # Verify interrupt was attempted
            mock_conn.interrupt.assert_called_once()


def test_sigint_between_cells_cancels_queue_and_raises() -> None:
    """SIGINT landing between two cells (scheduler still running its
    queue, no cell installed in `execution_context`) must halt the
    queue and raise `MarimoInterrupt`. Regression for the P2 where the
    handler returned early on `execution_context is None` before
    consulting `active_scheduler`."""
    sched = MagicMock()
    sched.has_active_tasks.return_value = False

    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = None
    ctx.active_scheduler = sched

    with patch("marimo._runtime.handlers.safe_get_context", return_value=ctx):
        interrupt_handler = construct_interrupt_handler()
        with pytest.raises(MarimoInterrupt):
            interrupt_handler(signal.SIGINT, None)

    sched.cancel_all.assert_called_once()


def test_sigint_with_active_async_task_cancels_without_raising() -> None:
    """When an async cell is in flight (scheduler reports active tasks),
    the handler must call `cancel_all` and return — raising from a
    signal handler would escape into asyncio internals and surface as
    an internal-error empty RunResult."""
    sched = MagicMock()
    sched.has_active_tasks.return_value = True

    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = None
    ctx.active_scheduler = sched

    with patch("marimo._runtime.handlers.safe_get_context", return_value=ctx):
        interrupt_handler = construct_interrupt_handler()
        # No exception raised.
        interrupt_handler(signal.SIGINT, None)

    sched.cancel_all.assert_called_once()


def test_sigint_with_no_scheduler_and_no_cell_is_noop() -> None:
    """No scheduler installed and no cell in flight — the handler must
    return silently without raising or calling broadcast."""
    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = None
    ctx.active_scheduler = None

    with patch("marimo._runtime.handlers.safe_get_context", return_value=ctx):
        interrupt_handler = construct_interrupt_handler()
        # No exception raised.
        interrupt_handler(signal.SIGINT, None)
