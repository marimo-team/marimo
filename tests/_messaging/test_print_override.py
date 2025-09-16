# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from marimo._messaging.print_override import print_override
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    ExecutionContext,
    RuntimeContext,
)
from marimo._runtime.threads import THREADS
from tests._messaging.mocks import MockStream


class TestPrintOverride:
    def test_print_override_normal(self) -> None:
        # Test print_override when not in a marimo thread
        with patch(
            "marimo._messaging.print_override._original_print"
        ) as mock_print:
            print_override("Hello, world!")
            mock_print.assert_called_once_with("Hello, world!")

    def test_print_override_with_thread_no_context(self) -> None:
        # Test print_override when in a marimo thread but no context
        thread_id = threading.get_ident()
        THREADS.add(thread_id)

        try:
            with patch(
                "marimo._messaging.print_override._original_print"
            ) as mock_print:
                with patch(
                    "marimo._messaging.print_override.get_context",
                    side_effect=ContextNotInitializedError,
                ):
                    print_override("Hello, world!")

                    # Original print should be called as a fallback
                    mock_print.assert_called_once_with("Hello, world!")
        finally:
            # Clean up
            if thread_id in THREADS:
                THREADS.remove(thread_id)

    def test_print_override_with_thread_and_context(self) -> None:
        # Test print_override when in a marimo thread with context
        thread_id = threading.get_ident()
        THREADS.add(thread_id)

        try:
            stream = MockStream()

            # Create a mock context
            context = MagicMock(spec=RuntimeContext)
            context.stream = stream
            context.execution_context = MagicMock(spec=ExecutionContext)
            context.execution_context.cell_id = "cell1"

            with patch(
                "marimo._messaging.print_override._original_print"
            ) as mock_print:
                with patch(
                    "marimo._messaging.print_override.get_context",
                    return_value=context,
                ):
                    print_override("Hello, world!")

                    # Original print should not be called
                    mock_print.assert_not_called()

                    # Message should be sent to the stream
                    assert len(stream.messages) == 1
                    assert stream.operations[0]["op"] == "cell-op"
                    assert stream.operations[0]["cell_id"] == "cell1"
                    assert (
                        stream.operations[0]["console"]["channel"] == "stdout"
                    )
                    assert (
                        stream.operations[0]["console"]["mimetype"]
                        == "text/plain"
                    )
                    assert (
                        stream.operations[0]["console"]["data"]
                        == "Hello, world!\n"
                    )
        finally:
            # Clean up
            if thread_id in THREADS:
                THREADS.remove(thread_id)

    def test_print_override_with_thread_no_execution_context(self) -> None:
        # Test print_override when in a marimo thread with context but no execution context
        thread_id = threading.get_ident()
        THREADS.add(thread_id)

        try:
            # Create a mock context with no execution context
            context = MagicMock(spec=RuntimeContext)
            context.execution_context = None

            with patch(
                "marimo._messaging.print_override._original_print"
            ) as mock_print:
                with patch(
                    "marimo._messaging.print_override.get_context",
                    return_value=context,
                ):
                    print_override("Hello, world!")

                    # Original print should be called
                    mock_print.assert_called_once_with("Hello, world!")
        finally:
            # Clean up
            if thread_id in THREADS:
                THREADS.remove(thread_id)

    def test_print_override_with_custom_sep_and_end(self) -> None:
        # Test print_override with custom separator and end
        thread_id = threading.get_ident()
        THREADS.add(thread_id)

        try:
            stream = MockStream()

            # Create a mock context
            context = MagicMock(spec=RuntimeContext)
            context.stream = stream
            context.execution_context = MagicMock(spec=ExecutionContext)
            context.execution_context.cell_id = "cell1"

            with patch(
                "marimo._messaging.print_override._original_print"
            ) as mock_print:
                with patch(
                    "marimo._messaging.print_override.get_context",
                    return_value=context,
                ):
                    print_override("Hello", "world", sep="-", end="!")

                    # Original print should not be called
                    mock_print.assert_not_called()

                    # Message should be sent to the stream with custom sep and end
                    assert len(stream.operations) == 1
                    assert (
                        stream.operations[0]["console"]["data"]
                        == "Hello-world!"
                    )
        finally:
            # Clean up
            if thread_id in THREADS:
                THREADS.remove(thread_id)

    def test_print_override_with_multiple_args(self) -> None:
        # Test print_override with multiple arguments
        thread_id = threading.get_ident()
        THREADS.add(thread_id)

        try:
            stream = MockStream()

            # Create a mock context
            context = MagicMock(spec=RuntimeContext)
            context.stream = stream
            context.execution_context = MagicMock(spec=ExecutionContext)
            context.execution_context.cell_id = "cell1"

            with patch(
                "marimo._messaging.print_override._original_print"
            ) as mock_print:
                with patch(
                    "marimo._messaging.print_override.get_context",
                    return_value=context,
                ):
                    print_override("Hello", 123, True, None)

                    # Original print should not be called
                    mock_print.assert_not_called()

                    # Message should be sent to the stream with all args converted to strings
                    assert len(stream.operations) == 1
                    assert (
                        stream.operations[0]["console"]["data"]
                        == "Hello 123 True None\n"
                    )
        finally:
            # Clean up
            if thread_id in THREADS:
                THREADS.remove(thread_id)
