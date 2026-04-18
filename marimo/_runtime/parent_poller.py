# Copyright 2026 Marimo. All rights reserved.
"""Poll another process and exit when that process exits.

Ported from ipykernel.parentpoller (BSD-licensed) to avoid orphaned kernel
processes when the marimo server is killed ungracefully (e.g. SIGKILL, OOM).
Without this, a crashed server can leave the kernel and its children running
forever.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from threading import Thread

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


class ParentPollerUnix(Thread):
    """Daemon thread that kills the process group when the parent has died.

    Two independent death-detection mechanisms:

    - `parent_pid`: watches the *direct* parent. When the direct parent exits,
      the OS reparents us (getppid becomes 1 or some other PID), which we can
      observe.

    - `ancestor_pid`: watches a non-parent PID.
    """

    def __init__(
        self,
        parent_pid: int,
        ancestor_pid: int | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.parent_pid = parent_pid
        self.ancestor_pid = ancestor_pid

    def _handle_parent_death(self) -> None:
        LOGGER.warning("Parent server appears to have exited, shutting down.")

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

    def _ancestor_is_gone(self) -> bool:
        if self.ancestor_pid is None or self.ancestor_pid <= 1:
            return False
        try:
            os.kill(self.ancestor_pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            # Ancestor exists but we no longer have permission to signal it
            # (e.g. PID reused by an unrelated user's process). Treat as gone.
            return True
        return False

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
                if (
                    parent_is_init
                    or parent_has_changed
                    or self._ancestor_is_gone()
                ):
                    self._handle_parent_death()
                    return
                time.sleep(1.0)
            except OSError as e:
                if e.errno == EINTR:
                    continue
                raise


def start_parent_poller(
    parent_pid: int | None,
    ancestor_pid: int | None = None,
) -> None:
    """Start a parent poller when the current Unix subprocess has a parent.

    Returns `None` when parent polling is not applicable, such as when
    running on Windows or when reparenting to PID 1 is expected.
    """
    if sys.platform == "win32" or parent_pid is None or parent_pid == 1:
        return

    ParentPollerUnix(parent_pid=parent_pid, ancestor_pid=ancestor_pid).start()
