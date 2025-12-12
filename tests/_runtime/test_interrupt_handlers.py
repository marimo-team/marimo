# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.errors import MarimoInterruptionError
from marimo._runtime.context.types import ExecutionContext
from marimo._runtime.handlers import construct_interrupt_handler

HAS_DUCKDB = DependencyManager.duckdb.has()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_interrupt_handler_called_when_connection_present():
    """Test that duckdb.interrupt() is called when a connection is present."""
    import duckdb

    # Create a mock connection that we can spy on
    mock_conn = MagicMock(spec=duckdb.DuckDBPyConnection)

    # Create an execution context with a duckdb connection
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)

    # Mock the context to return our execution context
    with patch("marimo._runtime.handlers.get_context") as mock_get_context:
        mock_context = MagicMock()
        mock_context.execution_context = exec_ctx
        mock_get_context.return_value = mock_context

        # Verify interrupt() is called when connection is set
        with exec_ctx.with_connection(mock_conn):
            interrupt_handler = construct_interrupt_handler(mock_context)

            # Trigger the interrupt handler
            with pytest.raises(MarimoInterruptionError):
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
    with patch("marimo._runtime.handlers.get_context") as mock_get_context:
        mock_context = MagicMock()
        mock_context.execution_context = exec_ctx
        mock_get_context.return_value = mock_context

        interrupt_handler = construct_interrupt_handler(mock_context)

        # Should not raise error from duckdb interrupt (only MarimoInterruptionError)
        with pytest.raises(MarimoInterruptionError):
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
    with patch("marimo._runtime.handlers.get_context") as mock_get_context:
        mock_context = MagicMock()
        mock_context.execution_context = exec_ctx
        mock_get_context.return_value = mock_context

        # Make interrupt() raise an exception
        with exec_ctx.with_connection(mock_conn):
            interrupt_handler = construct_interrupt_handler(mock_context)

            # Should raise MarimoInterruptionError, not RuntimeError
            # The RuntimeError should be caught and logged
            with pytest.raises(MarimoInterruptionError):
                interrupt_handler(signal.SIGINT, None)

            # Verify interrupt was attempted
            mock_conn.interrupt.assert_called_once()
