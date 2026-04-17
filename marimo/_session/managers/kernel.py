# Copyright 2026 Marimo. All rights reserved.
"""Kernel manager implementation using multiprocessing Process or threading Thread."""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from multiprocessing import connection, get_context
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import commands, runtime
from marimo._session.managers._shutdown import (
    ProcessShutdownController,
)
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike
from marimo._session.types import KernelManager, QueueManager
from marimo._utils.print import print_
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._runtime.commands import AppMetadata
    from marimo._runtime.virtual_file import VirtualFileStorageType
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


class KernelManagerImpl(KernelManager):
    """Kernel manager using multiprocessing Process or threading Thread.

    Uses Process for edit mode (allows SIGINT interrupts) and Thread for
    run mode (lower memory overhead).
    """

    def __init__(
        self,
        *,
        queue_manager: QueueManager,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        config_manager: MarimoConfigReader,
        virtual_file_storage: VirtualFileStorageType | None,
        redirect_console_to_browser: bool,
    ) -> None:
        self.kernel_task: ProcessLike | threading.Thread | None = None
        self.queue_manager = queue_manager
        self.mode = mode
        self.configs = configs
        self.app_metadata = app_metadata
        self.config_manager = config_manager
        self.redirect_console_to_browser = redirect_console_to_browser

        # Only used in edit mode
        self._read_conn: TypedConnection[KernelMessage] | None = None
        self._virtual_file_storage = virtual_file_storage
        self._process_shutdown = ProcessShutdownController(
            close_queues=self.queue_manager.close_queues
        )

    def start_kernel(self) -> None:
        # We use a process in edit mode so that we can interrupt the app
        # with a SIGINT; we don't mind the additional memory consumption,
        # since there's only one client session
        is_edit_mode = self.mode == SessionMode.EDIT
        listener = None
        if is_edit_mode:
            # Need to use a socket for windows compatibility
            listener = connection.Listener(family="AF_INET")
            self.kernel_task = get_context("spawn").Process(
                target=runtime.launch_kernel,
                args=(
                    self.queue_manager.control_queue,
                    self.queue_manager.set_ui_element_queue,
                    self.queue_manager.completion_queue,
                    self.queue_manager.input_queue,
                    # stream queue unused
                    None,
                    listener.address,
                    is_edit_mode,
                    self.configs,
                    self.app_metadata,
                    self.config_manager.get_config(hide_secrets=False),
                    self._virtual_file_storage,
                    self.redirect_console_to_browser,
                    self.queue_manager.win32_interrupt_queue,
                    self.profile_path,
                    GLOBAL_SETTINGS.LOG_LEVEL,
                ),
                kwargs={"parent_pid": os.getpid()},
                # The process can't be a daemon, because daemonic processes
                # can't create children
                # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process.daemon
                daemon=False,
            )
        else:
            # We use threads in run mode to minimize memory consumption;
            # launching a process would copy the entire program state,
            # which (as of writing) is around 150MB

            # We can't terminate threads, so we have to wait until they
            # naturally exit before cleaning up resources
            def launch_kernel_with_cleanup(
                *args: Any,
            ) -> None:
                runtime.launch_kernel(*args)

            # install formatter import hooks, which will be shared by all
            # threads (in edit mode, the single kernel process installs
            # formatters ...)
            register_formatters(theme=self.config_manager.theme)

            if self.redirect_console_to_browser:
                from marimo._messaging.thread_local_streams import (
                    install_thread_local_proxies,
                )

                install_thread_local_proxies()

            assert self.queue_manager.stream_queue is not None
            # Make threads daemons so killing the server immediately brings
            # down all client sessions
            self.kernel_task = threading.Thread(
                target=launch_kernel_with_cleanup,
                args=(
                    self.queue_manager.control_queue,
                    self.queue_manager.set_ui_element_queue,
                    self.queue_manager.completion_queue,
                    self.queue_manager.input_queue,
                    self.queue_manager.stream_queue,
                    # IPC not used in run mode
                    None,
                    is_edit_mode,
                    self.configs,
                    self.app_metadata,
                    self.config_manager.get_config(hide_secrets=False),
                    self._virtual_file_storage,
                    self.redirect_console_to_browser,
                    # win32 interrupt queue
                    None,
                    # profile path
                    None,
                    # log level
                    GLOBAL_SETTINGS.LOG_LEVEL,
                ),
                # daemon threads can create child processes, unlike
                # daemon processes
                daemon=True,
            )

        self.kernel_task.start()  # type: ignore
        if (
            sys.platform != "win32"
            and self.kernel_task is not None
            and not isinstance(self.kernel_task, threading.Thread)
        ):
            kernel_task = cast(ProcessLike, self.kernel_task)
            # The kernel calls setsid() during startup, so its eventual pgid
            # should match its pid; keep that as a fallback before we can safely observe it.
            self._process_shutdown.remember_expected_pgid(kernel_task.pid)
        if listener is not None:
            # First thing kernel does is connect to the socket, so it's safe to
            # call accept
            self._read_conn = TypedConnection[KernelMessage].of(
                listener.accept()
            )

    @property
    def pid(self) -> int | None:
        """Get the PID of the kernel."""
        if self.kernel_task is None:
            return None
        if isinstance(self.kernel_task, threading.Thread):
            return None
        return self.kernel_task.pid

    @property
    def profile_path(self) -> str | None:
        self._profile_path: str | None

        if hasattr(self, "_profile_path"):
            return self._profile_path

        profile_dir = GLOBAL_SETTINGS.PROFILE_DIR
        if profile_dir is not None:
            self._profile_path = os.path.join(
                profile_dir,
                (
                    os.path.basename(self.app_metadata.filename) + str(uuid4())
                    if self.app_metadata.filename is not None
                    else str(uuid4())
                ),
            )
        else:
            self._profile_path = None
        return self._profile_path

    def is_alive(self) -> bool:
        return self.kernel_task is not None and self.kernel_task.is_alive()

    def interrupt_kernel(self) -> None:
        if self.kernel_task is None:
            return

        if isinstance(self.kernel_task, threading.Thread):
            # no interruptions in run mode
            return

        if self.kernel_task.pid is not None:
            q = self.queue_manager.win32_interrupt_queue
            if sys.platform == "win32" and q is not None:
                LOGGER.debug("Queueing interrupt request for kernel.")
                q.put_nowait(True)
            else:
                LOGGER.debug("Sending SIGINT to kernel")
                os.kill(self.kernel_task.pid, signal.SIGINT)

    def _signal_kernel_tree(self, sig: int) -> None:
        """Best-effort signal delivery to the kernel process tree.

        For subprocess kernels on Unix, the runtime calls `setsid()` during
        startup so the kernel becomes the leader of its own process group.
        That lets the manager escalate from a cooperative shutdown request to
        process-group signaling, which reaches subprocesses spawned by user
        code. The helper in `process_tree.py` also handles the early-startup
        race where the child has not reached `setsid()` yet.
        """
        assert self.kernel_task is not None
        if isinstance(self.kernel_task, threading.Thread):
            return

        # Resolve pgid lazily. Caching is unsafe until the child has reached
        # setsid(); the shared helper keeps the early-startup fallback to a
        # direct pid signal so we never hit the server's own process group.
        self._process_shutdown.signal_tree(
            self.kernel_task.pid,
            sig,
            on_windows=self._terminate_kernel_on_windows,
        )

    def _terminate_kernel_on_windows(self, _: int) -> None:
        assert self.kernel_task is not None
        assert not isinstance(self.kernel_task, threading.Thread)
        try:
            self.kernel_task.terminate()
        except OSError:
            pass

    def _close_read_connection(self) -> None:
        """Close the IPC connection used to receive kernel messages."""
        if self._read_conn is not None:
            self._read_conn.close()
            self._read_conn = None

    def _close_queues(self) -> None:
        """Close queue resources exactly once."""
        self._process_shutdown.close_queues_once()

    def _wait_for_process_exit(self, timeout: float) -> bool:
        assert self.kernel_task is not None
        assert not isinstance(self.kernel_task, threading.Thread)
        self.kernel_task.join(timeout=timeout)
        return not self.kernel_task.is_alive()

    def _request_kernel_stop(self) -> None:
        profile_path = self.profile_path
        # Politely ask the kernel to stop; shutdown escalation happens
        # synchronously below in `close_kernel()`.
        self.queue_manager.put_control_request(commands.StopKernelCommand())
        if profile_path is not None:
            # Hack: block until the profile is written
            print_(f"\tWriting profile statistics to {profile_path} ...")
            while not os.path.exists(profile_path):
                time.sleep(0.1)

    def close_kernel(self) -> None:
        assert self.kernel_task is not None, "kernel not started"

        if isinstance(self.kernel_task, threading.Thread):
            # in run mode
            if self.kernel_task.is_alive():
                # We don't join the kernel thread because we don't want the
                # server to block on it finishing.
                self.queue_manager.put_control_request(
                    commands.StopKernelCommand()
                )
            return

        if not self.kernel_task.is_alive():
            # Kernel already exited; just release parent-side resources.
            self._close_queues()
            self._close_read_connection()
            return

        self._request_kernel_stop()
        # Block until the kernel exits (force-killing if necessary) and its
        # process group is reaped. See `ProcessShutdownController.run_shutdown`
        # for the escalation schedule.
        self._process_shutdown.run_shutdown(
            wait_for_exit=self._wait_for_process_exit,
            is_alive=self.kernel_task.is_alive,
            signal_tree=self._signal_kernel_tree,
            finalize=self._close_read_connection,
        )

    def wait_for_close(self, timeout: float | None = None) -> None:
        """No-op: `close_kernel()` now waits synchronously."""
        del timeout

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        assert self._read_conn is not None, "connection not started"
        return self._read_conn
