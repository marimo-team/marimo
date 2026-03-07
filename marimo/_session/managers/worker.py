# Copyright 2026 Marimo. All rights reserved.
"""Worker process management for per-app process isolation.

WorkerProcess: wraps a single multiprocessing.Process for one notebook.
WorkerProcessPool: manages workers keyed by absolute file path.
WorkerKernelManager: implements KernelManager protocol for worker-backed kernels.
"""

from __future__ import annotations

import os
import threading
from multiprocessing import get_context
from typing import TYPE_CHECKING, Optional, Union

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._session.managers.worker_commands import (
    CreateKernelCmd,
    KernelCreatedResponse,
    ShutdownWorkerCmd,
    StopKernelCmd,
)
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike
from marimo._session.types import KernelManager, QueueManager
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    import multiprocessing as mp

    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._ipc.types import ConnectionInfo
    from marimo._runtime.commands import AppMetadata
    from marimo._session.managers.ipc import IPCQueueManagerImpl
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()

_RESPONSE_TIMEOUT = 30  # seconds


class WorkerProcess:
    """Wraps a multiprocessing.Process for a single notebook file."""

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self._process: mp.Process | None = None
        self._mgmt_queue: mp.Queue[object] | None = None
        self._response_queue: mp.Queue[object] | None = None

    def start(self) -> None:
        from marimo._session.managers.worker_entry import worker_main

        ctx = get_context("spawn")
        self._mgmt_queue = ctx.Queue()
        self._response_queue = ctx.Queue()

        self._process = ctx.Process(
            target=worker_main,
            args=(
                self._mgmt_queue,
                self._response_queue,
                self._file_path,
                GLOBAL_SETTINGS.LOG_LEVEL,
            ),
            daemon=True,
        )
        self._process.start()
        LOGGER.debug(
            "Worker process started for %s (pid=%s)",
            self._file_path,
            self._process.pid,
        )

    def create_kernel(
        self,
        session_id: str,
        connection_info: ConnectionInfo,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        user_config: object,
        virtual_files_supported: bool,
        redirect_console_to_browser: bool,
        log_level: int,
    ) -> KernelCreatedResponse:
        assert self._mgmt_queue is not None
        assert self._response_queue is not None

        cmd = CreateKernelCmd(
            session_id=session_id,
            connection_info=connection_info,
            configs=configs,
            app_metadata=app_metadata,
            user_config=user_config,  # type: ignore[arg-type]
            virtual_files_supported=virtual_files_supported,
            redirect_console_to_browser=redirect_console_to_browser,
            log_level=log_level,
        )
        self._mgmt_queue.put(cmd)

        response = self._response_queue.get(timeout=_RESPONSE_TIMEOUT)
        assert isinstance(response, KernelCreatedResponse)
        return response

    def stop_kernel(self, session_id: str) -> None:
        if self._mgmt_queue is not None:
            self._mgmt_queue.put(StopKernelCmd(session_id=session_id))

    def is_alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    def shutdown(self) -> None:
        if self._mgmt_queue is not None:
            try:
                self._mgmt_queue.put(ShutdownWorkerCmd())
            except Exception:
                pass

        if self._process is not None:
            self._process.join(timeout=5)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=2)
                if self._process.is_alive():
                    self._process.kill()

        LOGGER.debug("Worker process shut down for %s", self._file_path)


class WorkerProcessPool:
    """Manages worker processes keyed by absolute file path."""

    def __init__(self) -> None:
        self._workers: dict[str, WorkerProcess] = {}
        self._lock = threading.Lock()

    def get_or_create(self, file_path: str) -> WorkerProcess:
        abs_path = os.path.abspath(file_path)
        with self._lock:
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                return worker

            # Dead worker or no worker — create a new one
            if worker is not None:
                LOGGER.warning(
                    "Worker for %s was dead, respawning", abs_path
                )

            worker = WorkerProcess(abs_path)
            worker.start()
            self._workers[abs_path] = worker
            return worker

    def shutdown(self) -> None:
        with self._lock:
            for worker in self._workers.values():
                worker.shutdown()
            self._workers.clear()


class _WorkerProcessLike(ProcessLike):
    """Makes WorkerProcess satisfy ProcessLike for kernel_task."""

    def __init__(self, worker: WorkerProcess) -> None:
        self._worker = worker

    @property
    def pid(self) -> int | None:
        return self._worker.pid

    def is_alive(self) -> bool:
        return self._worker.is_alive()

    def terminate(self) -> None:
        pass  # Don't terminate the shared worker from here

    def join(self, timeout: Optional[float] = None) -> None:
        pass  # Don't join the shared worker from here


class WorkerKernelManager(KernelManager):
    """KernelManager backed by a worker subprocess.

    The kernel runs as a thread inside the worker process.
    Communication happens via ZeroMQ channels.
    """

    def __init__(
        self,
        *,
        worker_pool: WorkerProcessPool,
        file_path: str,
        session_id: str,
        connection_info: ConnectionInfo,
        queue_manager: IPCQueueManagerImpl,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        config_manager: MarimoConfigReader,
        redirect_console_to_browser: bool,
    ) -> None:
        self._worker_pool = worker_pool
        self._file_path = file_path
        self._session_id = session_id
        self._connection_info = connection_info
        self.queue_manager = queue_manager
        self.mode = mode
        self._configs = configs
        self._app_metadata = app_metadata
        self._config_manager = config_manager
        self._redirect_console_to_browser = redirect_console_to_browser

        self._worker: WorkerProcess | None = None
        self.kernel_task: Optional[Union[ProcessLike, threading.Thread]] = None

    def start_kernel(self) -> None:
        self._worker = self._worker_pool.get_or_create(self._file_path)

        response = self._worker.create_kernel(
            session_id=self._session_id,
            connection_info=self._connection_info,
            configs=self._configs,
            app_metadata=self._app_metadata,
            user_config=self._config_manager.get_config(hide_secrets=False),
            virtual_files_supported=True,
            redirect_console_to_browser=self._redirect_console_to_browser,
            log_level=GLOBAL_SETTINGS.LOG_LEVEL,
        )

        if not response.success:
            raise RuntimeError(
                f"Failed to create kernel in worker: {response.error}"
            )

        self.kernel_task = _WorkerProcessLike(self._worker)

    @property
    def pid(self) -> int | None:
        if self._worker is None:
            return None
        return self._worker.pid

    @property
    def profile_path(self) -> str | None:
        return None

    def is_alive(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def interrupt_kernel(self) -> None:
        # Run-mode threads can't be interrupted (same as current behavior)
        pass

    def close_kernel(self) -> None:
        # Send stop via ZMQ control queue first
        from marimo._runtime.commands import StopKernelCommand

        self.queue_manager.put_control_request(StopKernelCommand())
        self.queue_manager.close_queues()

        # Also notify the worker via management channel
        if self._worker is not None:
            self._worker.stop_kernel(self._session_id)

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        # Worker kernels use stream_queue, not kernel_connection
        raise NotImplementedError(
            "Worker kernel uses stream_queue, not kernel_connection"
        )
