# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import signal
import sys
import time
from typing import TYPE_CHECKING

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._utils.print import (
    TAB,
    print_,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

_INTERRUPT_DEBOUNCE_SECONDS = 0.1
_SHUTDOWN_INTERRUPT_GRACE_SECONDS = 1.0


class InterruptHandler:
    def __init__(self, quiet: bool, shutdown: Callable[[], None]) -> None:
        self.quiet = quiet
        self.shutdown = shutdown
        self.loop = asyncio.get_running_loop()
        self.original_handler = signal.getsignal(signal.SIGINT)
        self._time_of_last_confirmation: float | None = None
        self._shutdown_started_at: float | None = None

    def stop(self) -> None:
        if self._shutdown_started_at is not None:
            return
        self._shutdown_started_at = time.monotonic()
        try:
            self.loop.remove_signal_handler(signal.SIGINT)
        except NotImplementedError:
            pass
        signal.signal(signal.SIGINT, self._interrupt_during_shutdown)

    def _interrupt_during_shutdown(
        self, signum: int, frame: FrameType | None
    ) -> None:
        assert self._shutdown_started_at is not None
        # uv can forward SIGINT after a delay; keep a later Ctrl-C available
        # to force quit if teardown stalls.
        if (
            time.monotonic() - self._shutdown_started_at
            >= _SHUTDOWN_INTERRUPT_GRACE_SECONDS
        ):
            signal.default_int_handler(signum, frame)

    def close(self) -> None:
        try:
            self.loop.remove_signal_handler(signal.SIGINT)
        except NotImplementedError:
            pass
        signal.signal(signal.SIGINT, self.original_handler)

    def _request_shutdown(self) -> None:
        if self._shutdown_started_at is not None:
            return
        self.stop()
        self.shutdown()

    def _add_interrupt_handler(self) -> None:
        try:
            self.loop.add_signal_handler(
                signal.SIGINT, self._interrupt_handler
            )
        except NotImplementedError:
            # Windows
            signal.signal(
                signal.SIGINT,
                lambda signum, frame: self._interrupt_handler(),  # noqa: ARG005
            )

    def _interrupt_handler(self) -> None:
        if self._shutdown_started_at is not None:
            return
        if (
            self._time_of_last_confirmation is not None
            and (time.time() - self._time_of_last_confirmation)
            < _INTERRUPT_DEBOUNCE_SECONDS
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
            self._request_shutdown()
            return

        try:
            try:
                if GLOBAL_SETTINGS.YES:
                    self._request_shutdown()
                    return

                # If not in an interactive terminal, just exit
                if not sys.stdin.isatty():
                    self._request_shutdown()
                    return

                response = input(
                    f"\r{TAB}Are you sure you want to quit? (y/N): "
                )
                self._time_of_last_confirmation = time.time()
                if response.lower().strip() == "y":
                    self._request_shutdown()
                    return
            except (KeyboardInterrupt, EOFError, asyncio.CancelledError):
                print_()
                self._request_shutdown()
                return
        except KeyboardInterrupt:
            # This is a hack to workaround the fact that uv can send two SIGINT for
            # every one entered by the user. Without this extra except block,
            # when running under uv, two Ctrl-C's from the user (which uv turns
            # into three) causes marimo to hang or abort unceremoniously instead
            # of cleanly exiting.
            print_()
            self._request_shutdown()
            return

        # Program is still alive: restore the interrupt handler
        self._add_interrupt_handler()

    def register(self) -> None:
        self._add_interrupt_handler()
