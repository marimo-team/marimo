# Copyright 2026 Marimo. All rights reserved.
"""Provides AppHosts for notebooks.

Each app is run in its own AppHost, providing isolation.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

from marimo import _loggers
from marimo._cli.sandbox import build_sandbox_venv, cleanup_sandbox_dir
from marimo._session._venv import get_ipc_kernel_deps
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

        # Build sandbox venv outside lock (can take many seconds)
        sandbox_dir, python = build_sandbox_venv(
            abs_path, additional_deps=get_ipc_kernel_deps()
        )

        with self._lock:
            # Re-check. Another thread may have created it while we were
            # building the venv
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
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


@dataclass(frozen=True)
class AppHostContext:
    """Everything a session needs to create its kernel inside an AppHost."""

    # The pool that provides the app host for a notebook
    pool: AppHostPool
    # The session ID corresponding to the kernel to create
    session_id: str
