# Copyright 2026 Marimo. All rights reserved.
"""Queue and Kernel managers for session management.

This module contains the infrastructure components for managing
kernel processes/threads and their associated communication queues.
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from multiprocessing import Process, connection, get_context
from multiprocessing.queues import Queue as MPQueue
from typing import Any, Optional, Union
from uuid import uuid4

from marimo import _loggers
from marimo._ast.cell import CellConfig
from marimo._config.manager import MarimoConfigReader
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import commands, runtime
from marimo._runtime.commands import AppMetadata
from marimo._server.model import SessionMode
from marimo._server.sessions.types import KernelManager, QueueManager
from marimo._server.types import ProcessLike
from marimo._server.utils import print_
from marimo._types.ids import CellId_t
from marimo._utils.typed_connection import TypedConnection

LOGGER = _loggers.marimo_logger()


class QueueManagerImpl(QueueManager):
    """Manages queues for a session."""

    def __init__(self, *, use_multiprocessing: bool):
        context = get_context("spawn") if use_multiprocessing else None

        # Control messages for the kernel (run, set UI element, set config, etc
        # ) are sent through the control queue
        self.control_queue: Union[
            MPQueue[commands.CommandMessage],
            queue.Queue[commands.CommandMessage],
        ] = context.Queue() if context is not None else queue.Queue()

        # Set UI element queues are stored in both the control queue and
        # this queue, so that the backend can merge/batch set-ui-element
        # requests.
        self.set_ui_element_queue: Union[
            MPQueue[commands.UpdateUIElementCommand],
            queue.Queue[commands.UpdateUIElementCommand],
        ] = context.Queue() if context is not None else queue.Queue()

        # Code completion requests are sent through a separate queue
        self.completion_queue: Union[
            MPQueue[commands.CodeCompletionCommand],
            queue.Queue[commands.CodeCompletionCommand],
        ] = context.Queue() if context is not None else queue.Queue()

        self.win32_interrupt_queue: (
            Union[MPQueue[bool], queue.Queue[bool]] | None
        )
        if sys.platform == "win32":
            self.win32_interrupt_queue = (
                context.Queue() if context is not None else queue.Queue()
            )
        else:
            self.win32_interrupt_queue = None

        # Input messages for the user's Python code are sent through the
        # input queue
        self.input_queue: Union[MPQueue[str], queue.Queue[str]] = (
            context.Queue(maxsize=1)
            if context is not None
            else queue.Queue(maxsize=1)
        )
        self.stream_queue: Optional[
            queue.Queue[Union[KernelMessage, None]]
        ] = None
        if not use_multiprocessing:
            self.stream_queue = queue.Queue()

    def close_queues(self) -> None:
        if isinstance(self.control_queue, MPQueue):
            # cancel join thread because we don't care if the queues still have
            # things in it: don't want to make the child process wait for the
            # queues to empty
            self.control_queue.cancel_join_thread()
            self.control_queue.close()
        else:
            # kernel thread cleans up read/write conn and IOloop handler on
            # exit; we don't join the thread because we don't want to block
            self.control_queue.put(commands.StopKernelCommand())

        if isinstance(self.set_ui_element_queue, MPQueue):
            self.set_ui_element_queue.cancel_join_thread()
            self.set_ui_element_queue.close()

        if isinstance(self.input_queue, MPQueue):
            # again, don't make the child process wait for the queues to empty
            self.input_queue.cancel_join_thread()
            self.input_queue.close()

        if isinstance(self.completion_queue, MPQueue):
            self.completion_queue.cancel_join_thread()
            self.completion_queue.close()

        if isinstance(self.win32_interrupt_queue, MPQueue):
            self.win32_interrupt_queue.cancel_join_thread()
            self.win32_interrupt_queue.close()

    def put_control_request(self, request: commands.CommandMessage) -> None:
        """Put a control request in the control queue."""
        # Completions are on their own queue
        if isinstance(request, commands.CodeCompletionCommand):
            self.completion_queue.put(request)
            return

        self.control_queue.put(request)
        # Update UI elements are on both queues so they can be batched
        if isinstance(request, commands.UpdateUIElementCommand):
            self.set_ui_element_queue.put(request)

    def put_input(self, text: str) -> None:
        """Put an input request in the input queue."""
        self.input_queue.put(text)


class KernelManagerImpl(KernelManager):
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
        self.kernel_task: Optional[ProcessLike | threading.Thread] = None
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
            def launch_kernel_with_cleanup(*args: Any) -> None:
                runtime.launch_kernel(*args)

            # install formatter import hooks, which will be shared by all
            # threads (in edit mode, the single kernel process installs
            # formatters ...)
            register_formatters(theme=self.config_manager.theme)

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


class ExternalQueueManagerAdapter(QueueManager):
    """Adapts IPC QueueManager to session QueueManager interface.

    This adapter wraps the ZeroMQ-based IPC QueueManager to provide
    the same interface as QueueManagerImpl for use with external kernels.
    """

    def __init__(self) -> None:
        # IPC queue manager is set later when kernel starts
        self._ipc: Any = None  # marimo._ipc.QueueManager

    def _ensure_ipc(self) -> Any:
        if self._ipc is None:
            raise RuntimeError("IPC queue manager not initialized")
        return self._ipc

    @property
    def control_queue(self) -> Any:
        return self._ensure_ipc().control_queue

    @property
    def set_ui_element_queue(self) -> Any:
        return self._ensure_ipc().set_ui_element_queue

    @property
    def completion_queue(self) -> Any:
        return self._ensure_ipc().completion_queue

    @property
    def input_queue(self) -> Any:
        return self._ensure_ipc().input_queue

    @property
    def stream_queue(self) -> Any:
        return self._ensure_ipc().stream_queue

    @property
    def win32_interrupt_queue(self) -> Any:
        return self._ensure_ipc().win32_interrupt_queue

    def close_queues(self) -> None:
        if self._ipc is not None:
            self._ipc.close_queues()

    def put_control_request(self, request: commands.CommandMessage) -> None:
        # Completions are on their own queue
        if isinstance(request, commands.CodeCompletionCommand):
            self.completion_queue.put(request)
            return

        self.control_queue.put(request)
        # Update UI elements are on both queues so they can be batched
        if isinstance(request, commands.UpdateUIElementCommand):
            self.set_ui_element_queue.put(request)

    def put_input(self, text: str) -> None:
        self.input_queue.put(text)


class ExternalKernelManager(KernelManager):
    """Kernel manager that runs kernel in external Python via ZeroMQ IPC.

    This manager launches a kernel subprocess using a different Python
    interpreter and communicates with it via ZeroMQ IPC channels.
    """

    def __init__(
        self,
        *,
        python_executable: str,
        queue_manager: ExternalQueueManagerAdapter,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        config_manager: MarimoConfigReader,
    ) -> None:
        self.python_executable = python_executable
        self.queue_manager = queue_manager
        self.mode = mode
        self.configs = configs
        self.app_metadata = app_metadata
        self.config_manager = config_manager

        self._process: subprocess.Popen[bytes] | None = None
        self._ipc_queue_manager: Any = None  # marimo._ipc.QueueManager
        self.kernel_task: ProcessLike | threading.Thread | None = None

    def start_kernel(self) -> None:
        from marimo._cli.external_env import (
            _check_marimo_installed,
            get_conda_env_vars,
            get_marimo_path,
        )
        from marimo._cli.print import echo, muted
        from marimo._ipc import QueueManager as IPCQueueManager
        from marimo._ipc.types import KernelArgs

        # Create ZeroMQ sockets (host side binds)
        self._ipc_queue_manager, connection_info = IPCQueueManager.create()

        # Update the adapter with the real queue manager
        self.queue_manager._ipc = self._ipc_queue_manager

        # Build kernel args
        kernel_args = KernelArgs(
            configs=self.configs,
            app_metadata=self.app_metadata,
            user_config=self.config_manager.get_config(hide_secrets=False),
            log_level=GLOBAL_SETTINGS.LOG_LEVEL,
            profile_path=None,
            connection_info=connection_info,
        )

        # Build environment
        env = os.environ.copy()
        env.update(get_conda_env_vars(self.python_executable))

        # Inject marimo and its IPC dependencies if not installed
        if not _check_marimo_installed(self.python_executable):
            from marimo._cli.external_env import get_required_dependency_paths

            # Collect all paths to inject
            inject_paths = [get_marimo_path()]
            inject_paths.extend(get_required_dependency_paths())

            existing = env.get("PYTHONPATH", "")
            new_paths = os.pathsep.join(inject_paths)
            if existing:
                env["PYTHONPATH"] = f"{new_paths}{os.pathsep}{existing}"
            else:
                env["PYTHONPATH"] = new_paths
            echo(
                f"Using external Python: {muted(self.python_executable)} "
                "(injecting marimo via PYTHONPATH)",
                err=True,
            )
        else:
            echo(
                f"Using external Python: {muted(self.python_executable)}",
                err=True,
            )

        # Launch kernel subprocess
        cmd = [self.python_executable, "-m", "marimo._ipc.launch_kernel"]
        LOGGER.debug(f"Launching external kernel: {' '.join(cmd)}")

        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        # Send connection info via stdin
        assert self._process.stdin is not None
        self._process.stdin.write(kernel_args.encode_json())
        self._process.stdin.flush()
        self._process.stdin.close()

        # Wait for ready signal
        assert self._process.stdout is not None
        ready = self._process.stdout.readline().decode().strip()
        if ready != "KERNEL_READY":
            assert self._process.stderr is not None
            stderr = self._process.stderr.read().decode()
            raise RuntimeError(
                f"External kernel failed to start.\n"
                f"Python: {self.python_executable}\n"
                f"Expected: KERNEL_READY\n"
                f"Got: {ready}\n"
                f"Stderr: {stderr}"
            )

        LOGGER.debug("External kernel ready")

        # Create a ProcessLike wrapper for the subprocess
        self.kernel_task = _SubprocessWrapper(self._process)

    @property
    def pid(self) -> int | None:
        if self._process is None:
            return None
        return self._process.pid

    @property
    def profile_path(self) -> str | None:
        # Profiling not supported for external kernels
        return None

    def is_alive(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    def interrupt_kernel(self) -> None:
        if self._process is None:
            return

        if self._process.pid is not None:
            q = self.queue_manager.win32_interrupt_queue
            if sys.platform == "win32" and q is not None:
                LOGGER.debug("Queueing interrupt request for external kernel.")
                q.put_nowait(True)
            else:
                LOGGER.debug("Sending SIGINT to external kernel")
                os.kill(self._process.pid, signal.SIGINT)

    def close_kernel(self) -> None:
        if self._process is None:
            return

        # Send stop command
        self.queue_manager.put_control_request(commands.StopKernelCommand())

        # Close queues
        self.queue_manager.close_queues()

        # Terminate process if still alive
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        # External kernel uses stream_queue instead of kernel_connection
        # This property should not be called for external kernels
        raise NotImplementedError(
            "External kernel uses stream_queue, not kernel_connection"
        )


class _SubprocessWrapper:
    """Wrapper to make subprocess.Popen compatible with ProcessLike."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process

    @property
    def pid(self) -> int | None:
        return self._process.pid

    def is_alive(self) -> bool:
        return self._process.poll() is None

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()
