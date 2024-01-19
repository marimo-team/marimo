# Copyright 2024 Marimo. All rights reserved.
import asyncio
import signal
from typing import Callable

from marimo._server.utils import (
    TAB,
)

ORIGINAL_SIGINT_HANDLER = signal.getsignal(signal.SIGINT)


class InterruptHandler:
    def __init__(self, quiet: bool, shutdown: Callable[[], None]) -> None:
        self.quiet = quiet
        self.shutdown = shutdown
        self.loop = asyncio.get_event_loop()

    def _interrupt_handler(self) -> None:
        # Restore the original signal handler so re-entering Ctrl+C raises a
        # keyboard interrupt instead of calling this function again (input is not
        # re-entrant, so it's not safe to call this function again)
        self.loop.remove_signal_handler(signal.SIGINT)
        if self.quiet:
            # self.loop.stop()
            self.shutdown()

        try:
            response = input(
                f"\r{TAB}\033[1;32mAre you sure you want to quit?\033[0m "
                "\033[1m(y/n)\033[0m: "
            )
            if response.lower().strip() == "y":
                # self.loop.stop()
                self.shutdown()
        except (KeyboardInterrupt, EOFError, asyncio.CancelledError):
            print()
            # self.loop.stop()
            self.shutdown()

        # Program is still alive: restore the interrupt handler
        self.loop.add_signal_handler(signal.SIGINT, self._interrupt_handler)

    def register(self) -> None:
        self.loop.add_signal_handler(signal.SIGINT, self._interrupt_handler)
