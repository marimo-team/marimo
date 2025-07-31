# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import signal
import sys
import time
from typing import Callable

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._server.utils import (
    TAB,
    print_,
)


class InterruptHandler:
    def __init__(self, quiet: bool, shutdown: Callable[[], None]) -> None:
        self.quiet = quiet
        self.shutdown = shutdown
        self.loop = asyncio.get_event_loop()
        self.original_handler = signal.getsignal(signal.SIGINT)
        self._time_of_last_confirmation: float | None = None

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

    def _interrupt_handler(self) -> None:
        if (
            self._time_of_last_confirmation is not None
            and (time.time() - self._time_of_last_confirmation) < 0.1
        ):
            # uv can send two SIGINTs for every one sent by the user's Ctrl+C;
            # this hack prevents us from spamming the user with confirm messages.
            return

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
            try:
                if GLOBAL_SETTINGS.YES:
                    self.shutdown()
                    return

                # If not in an interactive terminal, just exit
                if not sys.stdin.isatty():
                    self.shutdown()
                    return

                response = input(
                    f"\r{TAB}Are you sure you want to quit? (y/n): "
                )
                self._time_of_last_confirmation = time.time()
                if response.lower().strip() == "y":
                    self.shutdown()
                    return
            except (KeyboardInterrupt, EOFError, asyncio.CancelledError):
                print_()
                self.shutdown()
                return
        except KeyboardInterrupt:
            # This is a hack to workaround the fact that uv can send two SIGINT for
            # every one entered by the user. Without this extra except block,
            # when running under uv, two Ctrl-C's from the user (which uv turns
            # into three) causes marimo to hang or abort unceremoniously instead
            # of cleanly exiting.
            print_()
            self.shutdown()
            return

        # Program is still alive: restore the interrupt handler
        self._add_interrupt_handler()

    def register(self) -> None:
        self._add_interrupt_handler()
