# Copyright 2026 Marimo. All rights reserved.
"""IPC-based managers using ZeroMQ.

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
    build_sandbox_venv,
    cleanup_sandbox_dir,
)
from marimo._config.config import VenvConfig
from marimo._config.manager import MarimoConfigReader
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session._venv import (
    check_python_version_compatibility,
    get_configured_venv_python,
    get_ipc_kernel_deps,
    get_kernel_pythonpath,
    has_marimo_installed,
    install_marimo_into_venv,
)
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike, QueueType
from marimo._session.types import KernelManager, QueueManager
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._ipc.queue_manager import QueueManager as IPCQueueManagerType
    from marimo._ipc.types import ConnectionInfo
    from marimo._runtime.commands import AppMetadata
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def _get_venv_config(config_manager: MarimoConfigReader) -> VenvConfig:
    """Get the [tool.marimo.venv] config from a config manager."""
    config = config_manager.get_config(hide_secrets=False)
    return cast(VenvConfig, config.get("venv", {}))


class KernelStartupError(Exception):
    """Raised when kernel subprocess fails to start."""


class IPCQueueManagerImpl(QueueManager):
    """Manages queues for a session via ZeroMQ IPC.

    This wraps the ZeroMQ-based IPC QueueManager to provide queues
    for communication with the kernel subprocess.
    """

    def __init__(self, ipc: IPCQueueManagerType) -> None:
        self._ipc = ipc

    @classmethod
    def from_ipc(cls, ipc: IPCQueueManagerType) -> IPCQueueManagerImpl:
        """Create an IPCQueueManagerImpl from an IPC queue manager."""
        return cls(ipc)

    @property
    def control_queue(  # type: ignore[override]
        self,
    ) -> QueueType[commands.CommandMessage]:
        return self._ipc.control_queue

    @property
    def set_ui_element_queue(  # type: ignore[override]
        self,
    ) -> QueueType[commands.UpdateUIElementCommand]:
        return self._ipc.set_ui_element_queue

    @property
    def completion_queue(  # type: ignore[override]
        self,
    ) -> QueueType[commands.CodeCompletionCommand]:
        return self._ipc.completion_queue

    @property
    def packages_queue(  # type: ignore[override]
        self,
    ) -> QueueType[commands.PackagesCommand]:
        return self._ipc.packages_queue

    @property
    def input_queue(  # type: ignore[override]
        self,
    ) -> QueueType[str]:
        return self._ipc.input_queue

    @property
    def stream_queue(  # type: ignore[override]
        self,
    ) -> QueueType[Union[KernelMessage, None]]:
        return cast(
            QueueType[Union[KernelMessage, None]],
            self._ipc.stream_queue,
        )

    @property
    def win32_interrupt_queue(  # type: ignore[override]
        self,
    ) -> Optional[QueueType[bool]]:
        return self._ipc.win32_interrupt_queue

    def close_queues(self) -> None:
        self._ipc.close_queues()

    def put_control_request(
        self, request: Union[commands.CommandMessage, commands.PackagesCommand]
    ) -> None:
        # Completions are on their own queue
        if isinstance(request, commands.CodeCompletionCommand):
            self.completion_queue.put(request)
            return

        # Package listing requests go to their own queue
        if isinstance(
            request,
            (
                commands.ListPackagesCommand,
                commands.PackagesDependencyTreeCommand,
            ),
        ):
            self.packages_queue.put(request)
            return

        self.control_queue.put(request)
        # Update UI elements are on both queues so they can be batched
        if isinstance(request, commands.UpdateUIElementCommand):
            self.set_ui_element_queue.put(request)

    def put_input(self, text: str) -> None:
        self.input_queue.put(text)


class IPCKernelManagerImpl(KernelManager):
    """IPC-based kernel manager to spawn sandboxed kernels.

    Launches the kernel as a subprocess and communicates via ZeroMQ channels.
    Each notebook gets its own sandboxed virtual environment.
    """

    def __init__(
        self,
        *,
        queue_manager: IPCQueueManagerImpl,
        connection_info: ConnectionInfo,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        config_manager: MarimoConfigReader,
        virtual_files_supported: bool = True,
        redirect_console_to_browser: bool = True,
    ) -> None:
        self.queue_manager = queue_manager
        self.connection_info = connection_info
        self.mode = mode
        self.configs = configs
        self.app_metadata = app_metadata
        self.config_manager = config_manager
        self.virtual_files_supported = virtual_files_supported
        self.redirect_console_to_browser = redirect_console_to_browser

        self._process: subprocess.Popen[bytes] | None = None
        self.kernel_task: ProcessLike | None = None
        self._sandbox_dir: str | None = None

    def start_kernel(self) -> None:
        from marimo._cli.print import echo, muted
        from marimo._ipc.types import KernelArgs

        kernel_args = KernelArgs(
            configs=self.configs,
            app_metadata=self.app_metadata,
            user_config=self.config_manager.get_config(hide_secrets=False),
            log_level=GLOBAL_SETTINGS.LOG_LEVEL,
            profile_path=None,
            connection_info=self.connection_info,
            virtual_files_supported=self.virtual_files_supported,
            redirect_console_to_browser=self.redirect_console_to_browser,
        )

        env = os.environ.copy()

        venv_config = _get_venv_config(self.config_manager)
        try:
            configured_python = get_configured_venv_python(
                venv_config, base_path=self.app_metadata.filename
            )
        except ValueError as e:
            raise KernelStartupError(str(e)) from e

        # Ephemeral sandboxes are always writable; configured venvs respect the
        # flag.
        writable = True

        # An explicitly configured venv takes precedence over an ephemeral
        # sandbox.
        if configured_python:
            echo(
                f"Using configured venv: {muted(configured_python)}",
                err=True,
            )
            venv_python = configured_python

            writable = venv_config.get("writable", False)

            # Configured environments are assumed to be read-only.
            # If not, then install marimo by default to ensure that the
            # environment can spawn a marimo kernel.
            if writable:
                try:
                    install_marimo_into_venv(venv_python)
                except Exception as e:
                    raise KernelStartupError(
                        f"Failed to install marimo into configured venv.\n\n{e}"
                    ) from e
            elif not has_marimo_installed(venv_python):
                # Check Python version compatibility for binary deps
                if not check_python_version_compatibility(venv_python):
                    # If we have gotten to this point
                    # - We have a prescribed venv
                    # - The venv is not writable
                    # - The venv does not contain marimo nor zmq
                    # As such there is nothing we can do, as we can't get marimo
                    # into the runtime without installing it somewhere else.
                    raise KernelStartupError(
                        f"Configured venv uses a different Python version than marimo.\n"
                        f"Binary dependencies (pyzmq, msgspec) aren't cross-version compatible.\n\n"
                        f"Options:\n"
                        f"  1. Set writable=true in [tool.marimo.venv] to allow marimo to install deps\n"
                        f"  2. Install marimo in your venv: uv pip install marimo --python {venv_python}\n"
                        f"  3. Remove [tool.marimo.venv].path to use an ephemeral sandbox instead"
                    )

                # Inject PYTHONPATH for marimo and dependencies from the
                # current runtime as a last chance effort to expose marimo
                # to the kernel.
                kernel_path = get_kernel_pythonpath()
                existing = env.get("PYTHONPATH", "")
                if existing:
                    env["PYTHONPATH"] = f"{kernel_path}{os.pathsep}{existing}"
                else:
                    env["PYTHONPATH"] = kernel_path
        else:
            # Fall back to building ephemeral sandbox venv
            # with IPC dependencies.
            # NB. "Ephemeral" sandboxes (or rather tmp sandboxes built by uv)
            # are always writable, and as such install marimo as a default,
            # making them much easier than a configured venv we cannot manage.
            try:
                self._sandbox_dir, venv_python = build_sandbox_venv(
                    self.app_metadata.filename,
                    additional_deps=get_ipc_kernel_deps(),
                )
            except Exception as e:
                cleanup_sandbox_dir(self._sandbox_dir)
                raise KernelStartupError(
                    f"Failed to build sandbox environment.\n\n{e}"
                ) from e

            echo(
                f"Running kernel in sandbox: {muted(venv_python)}",
                err=True,
            )

        cmd = [venv_python, "-m", "marimo._ipc.launch_kernel"]
        if writable:
            # Setting this attempts to make auto-installations work even if
            # other normally detected criteria are not true.
            # IPC by itself does not seem to trigger them.
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
        except KernelStartupError:
            # Already a KernelStartupError, just cleanup and re-raise
            cleanup_sandbox_dir(self._sandbox_dir)
            raise
        except Exception as e:
            # Wrap other exceptions as KernelStartupError
            cleanup_sandbox_dir(self._sandbox_dir)
            raise KernelStartupError(
                f"Failed to start kernel subprocess.\n\n{e}"
            ) from e

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
        if self._process is not None:
            self.queue_manager.put_control_request(
                commands.StopKernelCommand()
            )
            self.queue_manager.close_queues()

            # Terminate process if still alive
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()

        # Always attempt cleanup, even if _process is None
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
