# Copyright 2026 Marimo. All rights reserved.
"""Shared helpers for subprocess-kernel shutdown."""

from __future__ import annotations

import signal
import sys
import time
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


class ProcessShutdownController:
    """Coordinates cooperative kernel shutdown and process-tree cleanup."""

    def __init__(self, *, close_queues: Callable[[], None]) -> None:
        self._close_queues = close_queues
        self._pgid: int | None = None
        self._expected_pgid: int | None = None
        self._queues_closed = False

    def remember_expected_pgid(self, pid: int | None) -> None:
        if sys.platform != "win32":
            self._expected_pgid = pid

    def signal_tree(
        self,
        pid: int | None,
        sig: int,
        *,
        terminate: Callable[[], None],
    ) -> None:
        """Signal the process tree rooted at `pid`.

        On POSIX, signals the full process group so subprocesses spawned by
        user code are reached. On Windows there is no process-group
        abstraction — escalation between SIGTERM and SIGKILL collapses to a
        single `TerminateProcess` call via `terminate()`.
        """
        if pid is None:
            return

        if sys.platform == "win32":
            try:
                terminate()
            except OSError:
                pass
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
        pid: int | None,
        wait_for_exit: Callable[[float], bool],
        is_alive: Callable[[], bool],
        terminate: Callable[[], None],
        finalize: Callable[[], None],
    ) -> None:
        try:
            self.close_queues_once()
            self.signal_tree(pid, signal.SIGTERM, terminate=terminate)
            wait_for_exit(_FORCE_SHUTDOWN_WAIT_SECONDS)

            if is_alive():
                kill_sig = (
                    signal.SIGKILL
                    if hasattr(signal, "SIGKILL")
                    else signal.SIGTERM
                )
                self.signal_tree(pid, kill_sig, terminate=terminate)
                wait_for_exit(_FORCE_SHUTDOWN_WAIT_SECONDS)

            self.reap_process_group_after_exit()
        finally:
            finalize()
