# Copyright 2026 Marimo. All rights reserved.
"""IPC-based managers for home sandbox mode using ZeroMQ.

These implementations launch the kernel as a subprocess and communicate
via ZeroMQ channels. Each notebook gets its own sandboxed virtual environment.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import TYPE_CHECKING, Optional, Union, cast

from marimo import _loggers
from marimo._cli.sandbox import (
    IPC_KERNEL_DEPS,
    build_sandbox_venv,
    cleanup_sandbox_dir,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike, QueueType
from marimo._session.types import KernelManager, QueueManager
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._ipc.queue_manager import QueueManager as IPCQueueManagerType
    from marimo._runtime.commands import AppMetadata
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


class KernelStartupError(Exception):
    """Raised when kernel subprocess fails to start."""

    pass


class IPCQueueManagerImpl(QueueManager):
    """Manages queues for a session via ZeroMQ IPC.

    This wraps the ZeroMQ-based IPC QueueManager to provide queues
    for communication with the kernel subprocess. Used for home sandbox mode.
    """

    def __init__(self) -> None:
        # IPC queue manager is set when kernel starts
        self._ipc: Optional[IPCQueueManagerType] = None

    def _ensure_ipc(self) -> IPCQueueManagerType:
        if self._ipc is None:
            raise RuntimeError("IPC queue manager not initialized")
        return self._ipc

    @property
    def control_queue(self) -> QueueType[commands.CommandMessage]:
        return self._ensure_ipc().control_queue

    @property
    def set_ui_element_queue(
        self,
    ) -> QueueType[commands.UpdateUIElementCommand]:
        return self._ensure_ipc().set_ui_element_queue

    @property
    def completion_queue(self) -> QueueType[commands.CodeCompletionCommand]:
        return self._ensure_ipc().completion_queue

    @property
    def input_queue(self) -> QueueType[str]:
        return self._ensure_ipc().input_queue

    @property
    def stream_queue(self) -> QueueType[Union[KernelMessage, None]]:
        return cast(
            QueueType[Union[KernelMessage, None]],
            self._ensure_ipc().stream_queue,
        )

    @property
    def win32_interrupt_queue(self) -> Optional[QueueType[bool]]:
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


class IPCKernelManagerImpl(KernelManager):
    """IPC-based kernel manager for home sandbox mode.

    Launches the kernel as a subprocess and communicates via ZeroMQ channels.
    Each notebook gets its own sandboxed virtual environment.
    """

    def __init__(
        self,
        *,
        queue_manager: IPCQueueManagerImpl,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        config_manager: MarimoConfigReader,
        virtual_files_supported: bool = True,
        redirect_console_to_browser: bool = True,
    ) -> None:
        self.queue_manager = queue_manager
        self.mode = mode
        self.configs = configs
        self.app_metadata = app_metadata
        self.config_manager = config_manager
        self.virtual_files_supported = virtual_files_supported
        self.redirect_console_to_browser = redirect_console_to_browser

        self._process: subprocess.Popen[bytes] | None = None
        self._ipc_queue_manager: Optional[IPCQueueManagerType] = None
        self.kernel_task: ProcessLike | None = None
        self._sandbox_dir: str | None = None

    def start_kernel(self) -> None:
        from marimo._cli.print import echo, muted
        from marimo._ipc import QueueManager as IPCQueueManager
        from marimo._ipc.types import KernelArgs

        # Create ZeroMQ sockets (host side binds)
        self._ipc_queue_manager, connection_info = IPCQueueManager.create()

        # Update the queue manager with the real IPC manager
        self.queue_manager._ipc = self._ipc_queue_manager

        # Build kernel args
        kernel_args = KernelArgs(
            configs=self.configs,
            app_metadata=self.app_metadata,
            user_config=self.config_manager.get_config(hide_secrets=False),
            log_level=GLOBAL_SETTINGS.LOG_LEVEL,
            profile_path=None,
            connection_info=connection_info,
            virtual_files_supported=self.virtual_files_supported,
            redirect_console_to_browser=self.redirect_console_to_browser,
        )

        # Build environment
        env = os.environ.copy()

        # Build sandbox venv with IPC dependencies
        try:
            self._sandbox_dir, venv_python = build_sandbox_venv(
                self.app_metadata.filename,
                additional_deps=IPC_KERNEL_DEPS,
            )
            cmd = [venv_python, "-m", "marimo._ipc.launch_kernel"]
        except Exception:
            cleanup_sandbox_dir(self._sandbox_dir)
            raise

        echo(
            f"Running kernel in sandbox: {muted(' '.join(cmd))}",
            err=True,
        )
        # Set MARIMO_MANAGE_SCRIPT_METADATA for sandbox
        env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"

        LOGGER.debug(f"Launching kernel: {' '.join(cmd)}")

        try:
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
                raise KernelStartupError(
                    f"Kernel failed to start.\n\n"
                    f"Command: {' '.join(cmd)}\n\n"
                    f"Stderr:\n{stderr}"
                )

            LOGGER.debug("Kernel ready")

            # Create a ProcessLike wrapper for the subprocess
            self.kernel_task = _SubprocessWrapper(self._process)
        except Exception:
            # Cleanup sandbox on any failure
            cleanup_sandbox_dir(self._sandbox_dir)
            raise

    @property
    def pid(self) -> int | None:
        if self._process is None:
            return None
        return self._process.pid

    @property
    def profile_path(self) -> str | None:
        # Profiling not currently supported with IPC kernel
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
                LOGGER.debug("Queueing interrupt request for kernel.")
                q.put_nowait(True)
            else:
                LOGGER.debug("Sending SIGINT to kernel")
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

        # Clean up sandbox directory
        cleanup_sandbox_dir(self._sandbox_dir)
        self._sandbox_dir = None

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        # IPC kernel uses stream_queue instead of kernel_connection
        raise NotImplementedError(
            "IPC kernel uses stream_queue, not kernel_connection"
        )


class _SubprocessWrapper(ProcessLike):
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

    def join(self, timeout: Optional[float] = None) -> None:
        self._process.wait(timeout=timeout)
