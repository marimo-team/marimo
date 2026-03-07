# Copyright 2026 Marimo. All rights reserved.
"""App process management for per-app process isolation.

AppProcess: wraps a single multiprocessing.Process for one notebook.
AppProcessPool: manages app processes keyed by absolute file path.
AppKernelManager: implements KernelManager protocol for app-process-backed kernels.
"""

from __future__ import annotations

import os
import threading
from multiprocessing import get_context
from typing import TYPE_CHECKING, Optional, Union

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._runtime.commands import StopKernelCommand
from marimo._session.managers.app_process_commands import (
    CreateKernelCmd,
    KernelCreatedResponse,
    ShutdownAppProcessCmd,
    StopKernelCmd,
)
from marimo._session.managers.app_process_entry import app_process_main
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike
from marimo._session.types import KernelManager
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from multiprocessing.context import SpawnProcess
    from multiprocessing.queues import Queue as MPQueue

    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._ipc.types import ConnectionInfo
    from marimo._runtime.commands import AppMetadata
    from marimo._session.managers.ipc import IPCQueueManagerImpl
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()

_RESPONSE_TIMEOUT = 30  # seconds


class AppProcess:
    """Wraps a multiprocessing.Process for a single notebook file."""

    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self._process: SpawnProcess | None = None
        self._mgmt_queue: MPQueue[object] | None = None
        self._response_queue: MPQueue[object] | None = None

    def start(self) -> None:
        ctx = get_context("spawn")
        self._mgmt_queue = ctx.Queue()
        self._response_queue = ctx.Queue()

        self._process = ctx.Process(
            target=app_process_main,
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
            "App process started for %s (pid=%s)",
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
                self._mgmt_queue.put(ShutdownAppProcessCmd())
            except Exception:
                pass

        if self._process is not None:
            self._process.join(timeout=5)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=2)
                if self._process.is_alive():
                    self._process.kill()

        LOGGER.debug("App process shut down for %s", self._file_path)


class AppProcessPool:
    """Manages app processes keyed by absolute file path.

    Each app is run in its own process to avoid collisions
    in sys.modules and other Python global data structures.
    """

    def __init__(self) -> None:
        self._workers: dict[str, AppProcess] = {}
        self._lock = threading.Lock()

    def get_or_create(self, file_path: str) -> AppProcess:
        abs_path = os.path.abspath(file_path)
        with self._lock:
            worker = self._workers.get(abs_path)
            if worker is not None and worker.is_alive():
                return worker

            # Dead process or no process — create a new one
            if worker is not None:
                LOGGER.warning(
                    "App process for %s was dead, respawning", abs_path
                )

            worker = AppProcess(abs_path)
            worker.start()
            self._workers[abs_path] = worker
            return worker

    def shutdown(self) -> None:
        with self._lock:
            for worker in self._workers.values():
                worker.shutdown()
            self._workers.clear()


class _AppProcessLike(ProcessLike):
    """Makes AppProcess satisfy ProcessLike for kernel_task."""

    def __init__(self, app_process: AppProcess) -> None:
        self._app_process = app_process

    @property
    def pid(self) -> int | None:
        return self._app_process.pid

    def is_alive(self) -> bool:
        return self._app_process.is_alive()

    def terminate(self) -> None:
        pass  # Don't terminate the shared app process from here

    def join(self, timeout: Optional[float] = None) -> None:
        pass  # Don't join the shared app process from here


class AppKernelManager(KernelManager):
    """KernelManager backed by an app subprocess.

    The kernel runs as a thread inside the app process.
    Communication happens via ZeroMQ channels.
    """

    def __init__(
        self,
        *,
        app_process_pool: AppProcessPool,
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
        self._app_process_pool = app_process_pool
        self._file_path = file_path
        self._session_id = session_id
        self._connection_info = connection_info
        self.queue_manager = queue_manager
        self.mode = mode
        self._configs = configs
        self._app_metadata = app_metadata
        self._config_manager = config_manager
        self._redirect_console_to_browser = redirect_console_to_browser

        self._app_process: AppProcess | None = None
        self.kernel_task: Optional[Union[ProcessLike, threading.Thread]] = None

    def start_kernel(self) -> None:
        self._app_process = self._app_process_pool.get_or_create(
            self._file_path
        )

        response = self._app_process.create_kernel(
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
                f"Failed to create kernel in app process: {response.error}"
            )

        self.kernel_task = _AppProcessLike(self._app_process)

    @property
    def pid(self) -> int | None:
        if self._app_process is None:
            return None
        return self._app_process.pid

    @property
    def profile_path(self) -> str | None:
        return None

    def is_alive(self) -> bool:
        return self._app_process is not None and self._app_process.is_alive()

    def interrupt_kernel(self) -> None:
        # Run-mode threads can't be interrupted (same as current behavior)
        pass

    def close_kernel(self) -> None:
        # Send stop via ZMQ control queue first
        self.queue_manager.put_control_request(StopKernelCommand())
        self.queue_manager.close_queues()

        # Also notify the app process via management channel
        if self._app_process is not None:
            self._app_process.stop_kernel(self._session_id)

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        # App process kernels use stream_queue, not kernel_connection
        raise NotImplementedError(
            "App process kernel uses stream_queue, not kernel_connection"
        )
