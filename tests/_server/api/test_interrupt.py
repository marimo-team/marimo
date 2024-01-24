# Copyright 2024 Marimo. All rights reserved.
from unittest.mock import Mock, patch

from marimo._server.api.interrupt import InterruptHandler


def test_interrupt_handler() -> None:
    shutdown_mock = Mock()

    # Create an instance of InterruptHandler with quiet mode disabled
    interrupt_handler = InterruptHandler(quiet=False, shutdown=shutdown_mock)

    # Register the interrupt handler
    interrupt_handler.register()

    # Simulate Ctrl+C signal
    interrupt_handler.loop.call_soon(interrupt_handler.loop.stop)
    interrupt_handler.loop.call_soon(interrupt_handler._interrupt_handler)

    # Run the event loop to process the signal
    interrupt_handler.loop.run_forever()

    # Assert that the shutdown callable was not called yet
    shutdown_mock.assert_not_called()

    # Simulate user input 'y' for yes
    with patch("builtins.input", return_value="y"):
        interrupt_handler.loop.call_soon(interrupt_handler.loop.stop)
        interrupt_handler.loop.call_soon(interrupt_handler._interrupt_handler)
        interrupt_handler.loop.run_forever()

    # Assert that the shutdown callable was called after user input
    shutdown_mock.assert_called_once()
