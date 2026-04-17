# Copyright 2026 Marimo. All rights reserved.
"""Watchdog threads that exit the kernel when the parent (server) dies.

Ported from ipykernel.parentpoller (BSD-licensed) to avoid orphaned kernel
processes when the marimo server is killed ungracefully (e.g. SIGKILL,
OOM). Without this, a crashed server leaves the kernel and its children
(jedi completion workers, multiprocessing spawn helpers) running forever.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from dataclasses import dataclass
from threading import Event, Thread
from typing import TYPE_CHECKING, Final

from marimo import _loggers

if TYPE_CHECKING:
    from collections.abc import Callable

LOGGER = _loggers.marimo_logger()

_PARENT_POLL_INTERVAL_SECONDS: Final[float] = 1.0
_PARENT_SHUTDOWN_WAIT_SECONDS: Final[float] = 1.0


@dataclass(frozen=True)
class ParentPollerHandle:
    """State shared between a parent poller and its owner."""

    exit_detected: Event
    cleanup_complete: Event

    def mark_cleanup_complete(self) -> None:
        """For the caller to signal to the poller it can exit."""
        self.cleanup_complete.set()

    def finalize_if_parent_died(self) -> None:
        if not self.exit_detected.is_set():
            return

        self.mark_cleanup_complete()
        kill_own_process_group()


def kill_own_process_group() -> None:
    """Force-kill this process and all peers in its process group."""
    try:
        os.killpg(os.getpgrp(), signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        LOGGER.debug(
            "Failed to kill kernel process group; exiting current process.",
            exc_info=True,
        )
    os._exit(1)


class ParentPollerUnix(Thread):
    """Daemon thread that exits the process when the parent has died."""

    def __init__(
        self,
        parent_pid: int,
        *,
        request_graceful_shutdown: Callable[[], None],
        parent_exit_detected: Event,
        cleanup_complete: Event,
        target_name: str = "kernel",
    ) -> None:
        super().__init__(daemon=True)
        self.parent_pid = parent_pid
        self.request_graceful_shutdown = request_graceful_shutdown
        self.parent_exit_detected = parent_exit_detected
        self.cleanup_complete = cleanup_complete
        self.target_name = target_name

    def _request_shutdown(self) -> None:
        try:
            self.request_graceful_shutdown()
        except Exception:
            LOGGER.debug(
                "Failed to request graceful shutdown during parent-death "
                "shutdown; force-kill fallback may be required.",
                exc_info=True,
            )

    def _handle_parent_death(self) -> None:
        LOGGER.warning(
            "Parent server appears to have exited, shutting down %s.",
            self.target_name,
        )
        self.parent_exit_detected.set()
        self._request_shutdown()

        if self.cleanup_complete.wait(timeout=_PARENT_SHUTDOWN_WAIT_SECONDS):
            return

        LOGGER.warning(
            "%s cleanup did not finish before timeout; force-killing its "
            "process group.",
            self.target_name.capitalize(),
        )
        kill_own_process_group()

    def run(self) -> None:
        from errno import EINTR

        # If the passed-in parent pid doesn't match our actual ppid,
        # fall back to detecting reparenting to init (ppid == 1).
        if os.getppid() != self.parent_pid:
            self.parent_pid = 0

        while True:
            try:
                ppid = os.getppid()
                parent_is_init = not self.parent_pid and ppid == 1
                parent_has_changed = (
                    self.parent_pid and ppid != self.parent_pid
                )
                if parent_is_init or parent_has_changed:
                    self._handle_parent_death()
                    return
                time.sleep(_PARENT_POLL_INTERVAL_SECONDS)
            except OSError as e:
                if e.errno == EINTR:
                    continue
                raise


def start_parent_poller(
    parent_pid: int | None,
    *,
    request_graceful_shutdown: Callable[[], None],
    target_name: str,
) -> ParentPollerHandle | None:
    """Start a parent poller when the current Unix subprocess has a parent.

    Returns ``None`` when parent polling is not applicable, such as when
    running on Windows or when reparenting to PID 1 is expected.
    """
    if sys.platform == "win32" or parent_pid in (None, 1):
        return None

    assert parent_pid is not None
    parent_pid_int = parent_pid
    handle = ParentPollerHandle(
        exit_detected=Event(),
        cleanup_complete=Event(),
    )
    ParentPollerUnix(
        parent_pid=parent_pid_int,
        request_graceful_shutdown=request_graceful_shutdown,
        parent_exit_detected=handle.exit_detected,
        cleanup_complete=handle.cleanup_complete,
        target_name=target_name,
    ).start()
    return handle
