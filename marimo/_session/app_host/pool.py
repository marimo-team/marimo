# Copyright 2026 Marimo. All rights reserved.
"""Provides AppHosts for notebooks.

Each app is run in its own AppHost, providing isolation.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

from marimo import _loggers
from marimo._environments.environment import (
    ProcessPlan,
    launch,
    launch_isolated,
    sync_notebook,
)
from marimo._environments.overlay import runtime_overlay
from marimo._environments.uv import UvMissingScriptMetadataError
from marimo._session.app_host.host import AppHost

LOGGER = _loggers.marimo_logger()


class AppHostPool:
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
                "Shutting down app host for %s (no active kernels)",
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
        """Get or create an AppHost with a sandboxed venv.

        Uses double-check locking: the venv build (which can take many
        seconds) runs outside the lock to avoid blocking other threads.
        """
        with self._lock:
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                return worker

        # Synchronize the script environment outside the lock (can take
        # many seconds); a notebook without a metadata block runs
        # ephemerally.
        args = ["-m", "marimo._session.app_host.main"]
        overlay = runtime_overlay()
        try:
            handle = sync_notebook(abs_path)
            plan = launch(handle, args, overlay=overlay)
        except UvMissingScriptMetadataError:
            import platform

            plan = launch_isolated(
                args, overlay=overlay, python=platform.python_version()
            )

        with self._lock:
            # Re-check. Another thread may have created it while we were
            # synchronizing.
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                return worker

            return self._create_locked(abs_path, plan=plan)

    def _create_locked(
        self,
        abs_path: str,
        plan: ProcessPlan | None = None,
    ) -> AppHost:
        """Create a new AppHost, replacing a dead one if present.

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
            plan=plan,
            on_empty=_on_empty,
        )
        worker.start()
        self._workers[abs_path] = worker
        return worker

    def shutdown(self) -> None:
        # Collect and clear under the lock, then shut down outside
        # it. worker.shutdown() can trigger _on_empty callbacks that
        # call _remove_and_shutdown, which also acquires self._lock;
        # Holding the lock here would deadlock.
        with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()

        for worker in workers:
            worker.shutdown()


@dataclass(frozen=True)
class AppHostContext:
    """Everything a session needs to create its kernel inside an AppHost."""

    # The pool that provides the app host for a notebook
    pool: AppHostPool
    # The session ID corresponding to the kernel to create
    session_id: str
