# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import signal
from typing import Callable

from marimo._server.utils import (
    TAB,
)


class InterruptHandler:
    def __init__(self, quiet: bool, shutdown: Callable[[], None]) -> None:
        self.quiet = quiet
        self.shutdown = shutdown
        self.loop = asyncio.get_event_loop()
        self.original_handler = signal.getsignal(signal.SIGINT)

    def _add_interrupt_handler(self) -> None:
        try:
            self.loop.add_signal_handler(
                signal.SIGINT, self._interrupt_handler
            )
        except NotImplementedError:
            # Windows
            signal.signal(
                signal.SIGINT,
                lambda signum, frame: self._interrupt_handler(),  # noqa: ARG005,E501
            )

    def restore_interrupt_handler(self) -> None:
        # Restore the original signal handler so re-entering Ctrl+C raises a
        # keyboard interrupt instead of calling this function again (input is
        # not re-entrant, so it's not safe to call this function again)
        try:
            self.loop.remove_signal_handler(signal.SIGINT)
        except NotImplementedError:
            # Windows
            signal.signal(signal.SIGINT, self.original_handler)

    def _interrupt_handler(self) -> None:
        # Restore the original signal handler so re-entering Ctrl+C raises a
        # keyboard interrupt instead of calling this function again (input is
        # not re-entrant, so it's not safe to call this function again)
        try:
            self.loop.remove_signal_handler(signal.SIGINT)
        except NotImplementedError:
            # Windows
            signal.signal(signal.SIGINT, self.original_handler)

        if self.quiet:
            self.shutdown()

        try:
            response = input(
                f"\r{TAB}\033[1;32mAre you sure you want to quit?\033[0m "
                "\033[1m(y/n)\033[0m: "
            )
            if response.lower().strip() == "y":
                self.shutdown()
                return
        except (KeyboardInterrupt, EOFError, asyncio.CancelledError):
            print()
            self.shutdown()
            return

        # Program is still alive: restore the interrupt handler
        self._add_interrupt_handler()

    def register(self) -> None:
        self._add_interrupt_handler()
