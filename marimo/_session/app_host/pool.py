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

    def __init__(self, sandbox: bool = False) -> None:
        self._workers: dict[str, AppHost] = {}
        self._lock = threading.Lock()
        self._sandbox = sandbox

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

        if self._sandbox:
            return self._get_or_create_sandboxed(abs_path)

        with self._lock:
            return self._create_locked(abs_path)

    def _get_or_create_sandboxed(self, abs_path: str) -> AppHost:
        """Get or create an app host with a sandboxed venv.

        Uses double-check locking: the venv build (which can take many
        seconds) runs outside the lock to avoid blocking other threads.
        """
        with self._lock:
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                return worker

        # Build sandbox venv outside lock (can take many seconds)
        from marimo._cli.sandbox import build_sandbox_venv
        from marimo._session._venv import get_ipc_kernel_deps

        sandbox_dir, python = build_sandbox_venv(
            abs_path, additional_deps=get_ipc_kernel_deps()
        )

        with self._lock:
            # Re-check — another thread may have created it while
            # we were building the venv
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                from marimo._cli.sandbox import cleanup_sandbox_dir

                cleanup_sandbox_dir(sandbox_dir)
                return worker

            return self._create_locked(
                abs_path, python=python, sandbox_dir=sandbox_dir
            )

    def _create_locked(
        self,
        abs_path: str,
        python: str | None = None,
        sandbox_dir: str | None = None,
    ) -> AppHost:
        """Create a new app host, replacing a dead one if present.

        Must be called while holding self._lock.
        """
        worker = self._workers.get(abs_path)
        if worker is not None and worker.is_alive():
            return worker

        if worker is not None:
            LOGGER.warning("App host for %s was dead, respawning", abs_path)
            worker.shutdown()

        def _on_empty() -> None:
            self._remove_and_shutdown(abs_path)

        worker = AppHost(
            abs_path,
            python=python,
            sandbox_dir=sandbox_dir,
            on_empty=_on_empty,
        )
        worker.start()
        self._workers[abs_path] = worker
        return worker

    def shutdown(self) -> None:
        with self._lock:
            for worker in self._workers.values():
                worker.shutdown()
            self._workers.clear()
