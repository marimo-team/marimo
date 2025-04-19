# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import signal
import sys
from typing import Callable

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._server.print import print_shutdown
from marimo._server.utils import (
    TAB,
    print_,
)


class InterruptHandler:
    def __init__(self, quiet: bool, shutdown: Callable[[], None]) -> None:
        self.quiet = quiet
        self._shutdown = shutdown
        self.loop = asyncio.get_event_loop()
        self.original_handler = signal.getsignal(signal.SIGINT)
        self._confirming_exit = False
        self._has_shutdown = False

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

    def shutdown(self) -> None:
        self._shutdown()
        self._has_shutdown = True

    async def _confirm_exit(self) -> None:
        try:
            self._confirming_exit = True
            print_()
            response = await asyncio.to_thread(
                input, f"\r{TAB}Are you sure you want to quit? (y/n): "
            )
            if response.lower().strip() == "y":
                print_()
                self.shutdown()
            else:
                self._confirming_exit = False
        except (EOFError, asyncio.CancelledError):
            print_()
            self.shutdown()

    def _interrupt_handler(self) -> None:
        if self._confirming_exit:
            print_()
            self.shutdown()
            print_shutdown()
            import os

            os._exit(0)

        if self.quiet:
            self.shutdown()
            return

        if GLOBAL_SETTINGS.YES:
            self.shutdown()
            return

        # self.loop.call_soon(self._confirm_exit)
        asyncio.create_task(self._confirm_exit())

    def register(self) -> None:
        self._add_interrupt_handler()
