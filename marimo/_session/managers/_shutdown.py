# Copyright 2026 Marimo. All rights reserved.
"""Shared helpers for subprocess-kernel shutdown."""

from __future__ import annotations

import signal
import sys
import threading
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from marimo._utils.process_tree import (
    signal_process_group,
    signal_process_tree,
)

_GRACEFUL_SHUTDOWN_WAIT_SECONDS = 1.0
_FORCE_SHUTDOWN_WAIT_SECONDS = 5.0
_PROCESS_GROUP_REAP_WAIT_SECONDS = 0.5


class BackgroundShutdownStartResult(Enum):
    STARTED = auto()
    ALREADY_STARTED = auto()
    TARGET_NOT_ALIVE = auto()


class ProcessShutdownController:
    """Coordinates cooperative kernel shutdown and process-tree cleanup."""

    def __init__(self, *, close_queues: Callable[[], None]) -> None:
        self._close_queues = close_queues
        self._pgid: int | None = None
        self._expected_pgid: int | None = None
        self._queues_closed = False
        self._shutdown_lock = threading.Lock()
        self._shutdown_thread: threading.Thread | None = None

    def remember_expected_pgid(self, pid: int | None) -> None:
        if sys.platform != "win32":
            self._expected_pgid = pid

    def signal_tree(
        self,
        pid: int | None,
        sig: int,
        *,
        on_windows: Callable[[int], None],
    ) -> None:
        if pid is None:
            return

        if sys.platform == "win32":
            on_windows(sig)
            return

        self._pgid = signal_process_tree(
            pid,
            sig,
            cached_pgid=self._pgid,
        )

    def close_queues_once(self) -> None:
        if self._queues_closed:
            return
        self._close_queues()
        self._queues_closed = True

    def reap_process_group_after_exit(self) -> None:
        if sys.platform == "win32":
            return

        pgid = self._pgid or self._expected_pgid
        if not signal_process_group(pgid, signal.SIGTERM):
            return

        kill_sig = (
            signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM
        )
        time.sleep(_PROCESS_GROUP_REAP_WAIT_SECONDS)
        signal_process_group(pgid, kill_sig)

    def run_shutdown(
        self,
        *,
        wait_for_exit: Callable[[float], bool],
        is_alive: Callable[[], bool],
        signal_tree: Callable[[int], None],
        finalize: Callable[[], None],
    ) -> None:
        try:
            if not wait_for_exit(_GRACEFUL_SHUTDOWN_WAIT_SECONDS):
                signal_tree(signal.SIGTERM)
                wait_for_exit(_FORCE_SHUTDOWN_WAIT_SECONDS)

            if is_alive():
                kill_sig = (
                    signal.SIGKILL
                    if hasattr(signal, "SIGKILL")
                    else signal.SIGTERM
                )
                signal_tree(kill_sig)
                wait_for_exit(_FORCE_SHUTDOWN_WAIT_SECONDS)

            self.reap_process_group_after_exit()
        finally:
            self.close_queues_once()
            finalize()

    def start_background_shutdown(
        self,
        *,
        is_alive: Callable[[], bool],
        target: Callable[[], None],
        before_start: Callable[[], None] | None = None,
    ) -> BackgroundShutdownStartResult:
        with self._shutdown_lock:
            if self._shutdown_thread is not None:
                return BackgroundShutdownStartResult.ALREADY_STARTED

            if not is_alive():
                return BackgroundShutdownStartResult.TARGET_NOT_ALIVE

            if before_start is not None:
                before_start()

            self._shutdown_thread = threading.Thread(
                target=target,
                daemon=False,
            )
            self._shutdown_thread.start()
            return BackgroundShutdownStartResult.STARTED

    def wait_for_shutdown(
        self,
        timeout: float | None,
        *,
        fallback_wait: Callable[[float | None], None],
    ) -> None:
        thread = self._shutdown_thread
        if thread is not None:
            thread.join(timeout=timeout)
            return

        fallback_wait(timeout)
