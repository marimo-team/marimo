# Copyright 2026 Marimo. All rights reserved.
"""Kernel manager implementation using multiprocessing Process or threading Thread."""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from multiprocessing import Process, connection
from typing import TYPE_CHECKING, Any, Optional, Union
from uuid import uuid4

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import commands, runtime
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike
from marimo._session.types import KernelManager, QueueManager
from marimo._utils.print import print_
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._runtime.commands import AppMetadata
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
        virtual_files_supported: bool,
        redirect_console_to_browser: bool,
    ) -> None:
        self.kernel_task: Optional[Union[ProcessLike, threading.Thread]] = None
        self.queue_manager = queue_manager
        self.mode = mode
        self.configs = configs
        self.app_metadata = app_metadata
        self.config_manager = config_manager
        self.redirect_console_to_browser = redirect_console_to_browser

        # Only used in edit mode
        self._read_conn: Optional[TypedConnection[KernelMessage]] = None
        self._virtual_files_supported = virtual_files_supported

    def start_kernel(self) -> None:
        # We use a process in edit mode so that we can interrupt the app
        # with a SIGINT; we don't mind the additional memory consumption,
        # since there's only one client session
        is_edit_mode = self.mode == SessionMode.EDIT
        listener = None
        if is_edit_mode:
            # Need to use a socket for windows compatibility
            listener = connection.Listener(family="AF_INET")
            self.kernel_task = Process(
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
                    self._virtual_files_supported,
                    self.redirect_console_to_browser,
                    self.queue_manager.win32_interrupt_queue,
                    self.profile_path,
                    GLOBAL_SETTINGS.LOG_LEVEL,
                ),
                # The process can't be a daemon, because daemonic processes
                # can't create children
                # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process.daemon  # noqa: E501
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
                from marimo._messaging.streams import (
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
                    self._virtual_files_supported,
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

    def close_kernel(self) -> None:
        assert self.kernel_task is not None, "kernel not started"

        if isinstance(self.kernel_task, threading.Thread):
            # in run mode
            if self.kernel_task.is_alive():
                # We don't join the kernel thread because we don't want to server
                # to block on it finishing
                self.queue_manager.put_control_request(
                    commands.StopKernelCommand()
                )
        else:
            # otherwise we have something that is `ProcessLike`
            if self.profile_path is not None and self.kernel_task.is_alive():
                self.queue_manager.put_control_request(
                    commands.StopKernelCommand()
                )
                # Hack: Wait for kernel to exit and write out profile;
                # joining the process hangs, but not sure why.
                print_(
                    "\tWriting profile statistics to",
                    self.profile_path,
                    " ...",
                )
                while not os.path.exists(self.profile_path):
                    time.sleep(0.1)
                time.sleep(1)

            self.queue_manager.close_queues()
            if self.kernel_task.is_alive():
                self.kernel_task.terminate()
            if self._read_conn is not None:
                self._read_conn.close()

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        assert self._read_conn is not None, "connection not started"
        return self._read_conn
