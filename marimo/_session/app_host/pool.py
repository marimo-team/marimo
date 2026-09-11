# Copyright 2026 Marimo. All rights reserved.
"""Provides AppHosts for notebooks.

Each app is run in its own AppHost, providing isolation.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import Future
from dataclasses import dataclass

from marimo._environments.environment import (
    ProcessPlan,
)
from marimo._environments.errors import (
    EnvironmentManagerError,
    MissingScriptMetadataError,
)
from marimo._environments.overlay import runtime_overlay
from marimo._session.app_host.host import AppHost
from marimo._session.managers.ipc import KernelStartupError


class AppHostPool:
    def __init__(self, sandbox: bool = False) -> None:
        self._workers: dict[str, AppHost] = {}
        self._lock = threading.Lock()
        self._sandbox = sandbox
        self._pending: dict[str, Future[AppHost]] = {}
        self._closed = False

    def _remove_and_shutdown(self, abs_path: str, worker: AppHost) -> None:
        # A delayed callback from a dead host must not remove its replacement.
        with self._lock:
            if self._workers.get(abs_path) is not worker:
                return
            del self._workers[abs_path]
        worker.shutdown()

    def get_or_create(self, file_path: str) -> AppHost:
        abs_path = os.path.abspath(file_path)
        with self._lock:
            if self._closed:
                raise KernelStartupError("App host pool is shut down")
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                return worker
            pending = self._pending.get(abs_path)
            owner = pending is None
            if pending is None:
                pending = Future()
                self._pending[abs_path] = pending

        if not owner:
            return pending.result()

        new_worker: AppHost | None = None
        try:
            if worker is not None:
                worker.shutdown()
            plan = self._sandbox_plan(abs_path) if self._sandbox else None
            with self._lock:
                if self._closed:
                    raise KernelStartupError("App host pool is shut down")
            new_worker = AppHost(
                abs_path,
                plan=plan,
                on_empty=lambda: self._remove_and_shutdown(abs_path, created),
            )
            created = new_worker
            new_worker.start()
            with self._lock:
                if self._closed:
                    raise KernelStartupError("App host pool is shut down")
                self._workers[abs_path] = new_worker
            pending.set_result(new_worker)
            return new_worker
        except BaseException as error:
            pending.set_exception(error)
            if new_worker is not None:
                new_worker.shutdown()
            raise
        finally:
            with self._lock:
                del self._pending[abs_path]

    def _sandbox_plan(self, abs_path: str) -> ProcessPlan:
        from marimo._environments import backends

        backend = backends.current_backend()
        args = ["-m", "marimo._session.app_host.main"]
        overlay = runtime_overlay()
        try:
            try:
                handle = backends.sync_notebook(abs_path, backend=backend)
            except MissingScriptMetadataError:
                plan = backends.launch_fallback(args)
                plan.env.pop("MARIMO_SANDBOX_MODE", None)
            else:
                plan = backends.launch(
                    handle, args, backend=backend, overlay=overlay
                )
                plan.env["MARIMO_SANDBOX_MODE"] = "multi"
            plan.env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"
            return plan
        except EnvironmentManagerError as error:
            raise KernelStartupError(str(error)) from error

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            workers = list(self._workers.values())
            self._workers.clear()
        # In-flight startups observe _closed before publishing and clean up.
        for worker in workers:
            worker.shutdown()


@dataclass(frozen=True)
class AppHostContext:
    """Everything a session needs to create its kernel inside an AppHost."""

    # The pool that provides the app host for a notebook
    pool: AppHostPool
    # The session ID corresponding to the kernel to create
    session_id: str
