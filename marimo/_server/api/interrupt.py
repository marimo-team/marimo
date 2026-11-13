# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
import threading
import time
from typing import TYPE_CHECKING

from marimo._config.settings import GLOBAL_SETTINGS
from marimo._utils.print import (
    TAB,
    print_,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import FrameType

_INTERRUPT_DEBOUNCE_SECONDS = 0.1
_SHUTDOWN_INTERRUPT_GRACE_SECONDS = 1.0


class InterruptHandler:
    def __init__(self, quiet: bool, shutdown: Callable[[], None]) -> None:
        self.quiet = quiet
        self.shutdown = shutdown
        self.loop = asyncio.get_running_loop()
        self.original_handler = signal.getsignal(signal.SIGINT)
        self._is_main_thread = (
            threading.current_thread() is threading.main_thread()
        )
        self._time_of_last_confirmation: float | None = None
        self._shutting_down = False

    @contextlib.contextmanager
    def listen(self) -> Iterator[None]:
        if not self._is_main_thread:
            yield
            return
        self._add_interrupt_handler()
        try:
            yield
        finally:
            self._remove_interrupt_handler()
            signal.signal(signal.SIGINT, self.original_handler)

    def begin_shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        if not self._is_main_thread:
            return
        force_quit_after = time.monotonic() + _SHUTDOWN_INTERRUPT_GRACE_SECONDS

        def interrupt_shutdown(signum: int, frame: FrameType | None) -> None:
            # uv forwards delayed duplicates; a later Ctrl-C can force quit,
            # even when synchronous cleanup blocks the event loop.
            if time.monotonic() >= force_quit_after:
                signal.default_int_handler(signum, frame)

        self._remove_interrupt_handler()
        signal.signal(signal.SIGINT, interrupt_shutdown)

    def _request_shutdown(self) -> None:
        if self._shutting_down:
            return
        self.begin_shutdown()
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

    def _remove_interrupt_handler(self) -> None:
        try:
            self.loop.remove_signal_handler(signal.SIGINT)
        except NotImplementedError:
            pass

    def _interrupt_handler(self) -> None:
        if self._shutting_down:
            return
        if (
            self._time_of_last_confirmation is not None
            and (time.monotonic() - self._time_of_last_confirmation)
            < _INTERRUPT_DEBOUNCE_SECONDS
        ):
            # uv can send two SIGINTs for every one sent by the user's Ctrl+C;
            # this hack prevents us from spamming the user with confirm messages.
            return

        if self.quiet or GLOBAL_SETTINGS.YES or not sys.stdin.isatty():
            self._request_shutdown()
            return

        # input() blocks the event loop, so Ctrl-C must interrupt it directly.
        self._remove_interrupt_handler()
        signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            response = input(f"\r{TAB}Are you sure you want to quit? (y/N): ")
        except (KeyboardInterrupt, EOFError):
            self._request_shutdown()
            print_()
            return

        self._time_of_last_confirmation = time.monotonic()
        if response.lower().strip() == "y":
            self._request_shutdown()
        else:
            self._add_interrupt_handler()
