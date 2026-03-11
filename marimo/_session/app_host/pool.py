# Copyright 2026 Marimo. All rights reserved.
"""AppHostPool: manages app host processes keyed by absolute file path.

Each app is run in its own process to avoid collisions
in sys.modules and other Python global data structures.
"""

from __future__ import annotations

import os
import threading

from marimo import _loggers
from marimo._session.app_host.host import AppHost

LOGGER = _loggers.marimo_logger()


class AppHostPool:
    """Manages app host processes keyed by absolute file path.

    Each app is run in its own process to avoid collisions
    in sys.modules and other Python global data structures.
    """

    def __init__(self) -> None:
        self._workers: dict[str, AppHost] = {}
        self._lock = threading.Lock()

    def _remove_and_shutdown(self, abs_path: str) -> None:
        """Remove an app host from the pool and shut it down.

        Called when the host has zero active kernels.
        """
        with self._lock:
            worker = self._workers.pop(abs_path, None)
        if worker is not None:
            LOGGER.debug(
                "Auto-shutting down app host for %s (no active kernels)",
                abs_path,
            )
            worker.shutdown()

    def get_or_create(self, file_path: str) -> AppHost:
        abs_path = os.path.abspath(file_path)
        with self._lock:
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                return worker

            # Dead host or no host — create a new one
            if worker is not None:
                LOGGER.warning(
                    "App host for %s was dead, respawning", abs_path
                )
                worker.shutdown()

            def _on_empty() -> None:
                self._remove_and_shutdown(abs_path)

            worker = AppHost(abs_path, on_empty=_on_empty)
            worker.start()
            self._workers[abs_path] = worker
            return worker

    def shutdown(self) -> None:
        with self._lock:
            for worker in self._workers.values():
                worker.shutdown()
            self._workers.clear()
