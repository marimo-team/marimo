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
from typing import TYPE_CHECKING, Optional, Union

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike
from marimo._session.types import KernelManager, QueueManager
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from queue import Queue

    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._ipc.queue_manager import QueueManager as IPCQueueManagerType
    from marimo._runtime.commands import AppMetadata
    from marimo._types.ids import CellId_t
    from marimo._utils.inline_script_metadata import PyProjectReader

LOGGER = _loggers.marimo_logger()


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
    def control_queue(self) -> Queue[commands.CommandMessage]:
        return self._ensure_ipc().control_queue

    @property
    def set_ui_element_queue(self) -> Queue[commands.UpdateUIElementCommand]:
        return self._ensure_ipc().set_ui_element_queue

    @property
    def completion_queue(self) -> Queue[commands.CodeCompletionCommand]:
        return self._ensure_ipc().completion_queue

    @property
    def input_queue(self) -> Queue[str]:
        return self._ensure_ipc().input_queue

    @property
    def stream_queue(self) -> Queue[Union[KernelMessage, None]]:
        return self._ensure_ipc().stream_queue

    @property
    def win32_interrupt_queue(self) -> Optional[Queue[bool]]:
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

        # Build sandbox command
        cmd = self._build_sandbox_command()
        from marimo._cli.print import echo, muted

        echo(
            f"Running kernel in sandbox: {muted(' '.join(cmd))}",
            err=True,
        )
        # Set MARIMO_MANAGE_SCRIPT_METADATA for sandbox
        env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"

        LOGGER.debug(f"Launching kernel: {' '.join(cmd)}")

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
                f"Kernel failed to start.\n"
                f"Expected: KERNEL_READY\n"
                f"Got: {ready}\n"
                f"Stderr: {stderr}"
            )

        LOGGER.debug("Kernel ready")

        # Create a ProcessLike wrapper for the subprocess
        self.kernel_task = _SubprocessWrapper(self._process)

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
        self._cleanup_sandbox()

    @property
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
        # IPC kernel uses stream_queue instead of kernel_connection
        raise NotImplementedError(
            "IPC kernel uses stream_queue, not kernel_connection"
        )

    def _build_sandbox_command(self) -> list[str]:
        """Build sandbox environment and return kernel launch command.

        Two-phase approach:
        1. Create ephemeral venv with dependencies using uv
        2. Return command to launch kernel with venv's Python

        This separates package installation output from kernel communication,
        ensuring "KERNEL_READY" signal is not mixed with uv's install logs.
        """
        import tempfile

        from marimo._cli.print import echo, muted
        from marimo._utils.inline_script_metadata import PyProjectReader
        from marimo._utils.uv import find_uv_bin

        uv_bin = find_uv_bin()
        filename = self.app_metadata.filename

        # Read dependencies from notebook
        pyproject = (
            PyProjectReader.from_filename(filename)
            if filename is not None
            else PyProjectReader({}, config_path=None)
        )

        # Create temp directory for sandbox venv
        self._sandbox_dir = tempfile.mkdtemp(prefix="marimo-sandbox-")
        venv_path = os.path.join(self._sandbox_dir, "venv")

        # Phase 1: Create venv
        echo(f"Creating sandbox environment: {muted(venv_path)}", err=True)
        subprocess.run(
            [uv_bin, "venv", "--seed", venv_path],
            check=True,
            capture_output=True,
        )

        # Get venv Python path
        if sys.platform == "win32":
            venv_python = os.path.join(venv_path, "Scripts", "python.exe")
        else:
            venv_python = os.path.join(venv_path, "bin", "python")

        # Phase 1b: Install dependencies
        # ALWAYS install - IPC mode requires pyzmq/msgspec for kernel communication
        requirements = self._get_sandbox_requirements(pyproject)
        echo("Installing sandbox dependencies...", err=True)

        # Separate editable installs from regular requirements
        # Editable installs look like "-e /path/to/package"
        editable_reqs = [r for r in requirements if r.startswith("-e ")]
        regular_reqs = [r for r in requirements if not r.startswith("-e ")]

        # Install editable packages directly (not via requirements file)
        for editable in editable_reqs:
            # Extract path from "-e /path/to/package"
            editable_path = editable[3:].strip()
            result = subprocess.run(
                [
                    uv_bin,
                    "pip",
                    "install",
                    "--python",
                    venv_python,
                    "-e",
                    editable_path,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                echo(
                    f"Warning: Editable install failed: {result.stderr}",
                    err=True,
                )

        # Install regular packages via requirements file
        if regular_reqs:
            req_file = os.path.join(self._sandbox_dir, "requirements.txt")
            with open(req_file, "w", encoding="utf-8") as f:
                f.write("\n".join(regular_reqs))

            result = subprocess.run(
                [
                    uv_bin,
                    "pip",
                    "install",
                    "--python",
                    venv_python,
                    "-r",
                    req_file,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to install sandbox dependencies: {result.stderr}"
                )

        # Phase 2: Return direct python command
        return [venv_python, "-m", "marimo._ipc.launch_kernel"]

    def _get_sandbox_requirements(
        self, pyproject: PyProjectReader
    ) -> list[str]:
        """Get normalized requirements for sandbox.

        In addition to notebook dependencies, we inject pyzmq and msgspec
        for IPC kernel communication.
        """
        from marimo import __version__
        from marimo._cli.sandbox import (
            _normalize_sandbox_dependencies,
            _resolve_requirements_txt_lines,
        )

        dependencies = _resolve_requirements_txt_lines(pyproject)
        normalized = _normalize_sandbox_dependencies(
            dependencies, __version__, additional_features=[]
        )

        # Add IPC dependencies (pyzmq, msgspec) if not already present
        # These are required for kernel <-> host communication
        # No version pins - let uv resolve compatible versions
        ipc_deps = ["pyzmq", "msgspec"]
        existing_lower = {
            d.lower().split("[")[0].split(">=")[0].split("==")[0]
            for d in normalized
        }

        for ipc_dep in ipc_deps:
            if ipc_dep.lower() not in existing_lower:
                normalized.append(ipc_dep)

        return normalized

    def _cleanup_sandbox(self) -> None:
        """Clean up sandbox directory."""
        import shutil

        if hasattr(self, "_sandbox_dir") and self._sandbox_dir:
            try:
                shutil.rmtree(self._sandbox_dir)
            except OSError:
                pass
            self._sandbox_dir = None


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
