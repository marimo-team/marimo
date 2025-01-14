# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from unittest.mock import Mock, patch

from marimo._server.api.interrupt import InterruptHandler


async def test_interrupt_handler() -> None:
    shutdown_mock = Mock()

    # Create an instance of InterruptHandler with quiet mode disabled
    interrupt_handler = InterruptHandler(quiet=False, shutdown=shutdown_mock)

    # Register the interrupt handler
    interrupt_handler.register()

    # Mock the input function before simulating Ctrl+C
    with patch("builtins.input", return_value="y"):
        # Simulate Ctrl+C signal
        interrupt_handler.loop.call_soon(interrupt_handler._interrupt_handler)
        await asyncio.sleep(0)  # Let the event loop process the signal

        # Assert that the shutdown callable was called
        shutdown_mock.assert_called_once()

    # Reset the mock for the next test
    shutdown_mock.reset_mock()

    # Test with 'n' response
    with patch("builtins.input", return_value="n"):
        # Simulate Ctrl+C signal
        interrupt_handler.loop.call_soon(interrupt_handler._interrupt_handler)
        await asyncio.sleep(0)  # Let the event loop process the signal

        # Assert that the shutdown callable was not called
        shutdown_mock.assert_not_called()
