# Copyright 2026 Marimo. All rights reserved.
"""Queue and Kernel managers for session management.

This module contains the infrastructure components for managing
kernel processes and their associated communication queues via ZeroMQ IPC.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._server.sessions.types import KernelManager, QueueManager
from marimo._server.types import ProcessLike
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._config.manager import MarimoConfigReader
    from marimo._runtime.commands import AppMetadata
    from marimo._server.model import SessionMode
    from marimo._types.ids import CellId_t
    from marimo._utils.inline_script_metadata import PyProjectReader

LOGGER = _loggers.marimo_logger()


class QueueManagerImpl(QueueManager):
    """Manages queues for a session via ZeroMQ IPC.

    This wraps the ZeroMQ-based IPC QueueManager to provide queues
    for communication with the kernel subprocess.
    """

    def __init__(self) -> None:
        # IPC queue manager is set when kernel starts
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


class KernelManagerImpl(KernelManager):
    """Manages kernel lifecycle via ZeroMQ IPC.

    Launches the kernel as a subprocess and communicates via ZeroMQ channels.
    Supports both the current Python interpreter and external Python environments.
    """

    def __init__(
        self,
        *,
        queue_manager: QueueManagerImpl,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        config_manager: MarimoConfigReader,
        python_executable: str | None = None,
        virtual_files_supported: bool = True,
        redirect_console_to_browser: bool = True,
        sandbox_mode: bool = False,
    ) -> None:
        # Use current Python if not specified
        self.python_executable = python_executable or sys.executable
        self.queue_manager = queue_manager
        self.mode = mode
        self.configs = configs
        self.app_metadata = app_metadata
        self.config_manager = config_manager
        self.virtual_files_supported = virtual_files_supported
        self.redirect_console_to_browser = redirect_console_to_browser
        self.sandbox_mode = sandbox_mode

        self._process: subprocess.Popen[bytes] | None = None
        self._ipc_queue_manager: Any = None  # marimo._ipc.QueueManager
        self.kernel_task: ProcessLike | None = None
        self._sandbox_dir: str | None = None

    def start_kernel(self) -> None:
        from marimo._cli.external_env import (
            _check_marimo_installed,
            get_conda_env_vars,
            get_marimo_path,
            is_same_python,
        )
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

        # Build command based on sandbox mode
        if self.sandbox_mode:
            cmd = self._build_sandbox_command()
            from marimo._cli.print import echo, muted

            echo(
                f"Running kernel in sandbox: {muted(' '.join(cmd))}",
                err=True,
            )
            # Set MARIMO_MANAGE_SCRIPT_METADATA for sandbox
            env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"
        else:
            env.update(get_conda_env_vars(self.python_executable))

            # Inject marimo and dependencies if not in same env or not installed
            is_external = not is_same_python(self.python_executable)
            needs_injection = is_external and not _check_marimo_installed(
                self.python_executable
            )

            if needs_injection:
                from marimo._cli.external_env import (
                    get_required_dependency_paths,
                )
                from marimo._cli.print import echo, muted

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
            elif is_external:
                from marimo._cli.print import echo, muted

                echo(
                    f"Using external Python: {muted(self.python_executable)}",
                    err=True,
                )

            # Launch kernel subprocess
            cmd = [self.python_executable, "-m", "marimo._ipc.launch_kernel"]

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
                f"Python: {self.python_executable}\n"
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

        # Clean up sandbox directory if in sandbox mode
        if self.sandbox_mode:
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
        requirements = self._get_sandbox_requirements(pyproject)
        if requirements:
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
                    echo(
                        f"Warning: Package install failed: {result.stderr}",
                        err=True,
                    )

        # Phase 2: Return direct python command
        return [venv_python, "-m", "marimo._ipc.launch_kernel"]

    def _get_sandbox_requirements(
        self, pyproject: PyProjectReader
    ) -> list[str]:
        """Get normalized requirements for sandbox."""
        from marimo import __version__
        from marimo._cli.sandbox import (
            _normalize_sandbox_dependencies,
            _resolve_requirements_txt_lines,
        )

        dependencies = _resolve_requirements_txt_lines(pyproject)
        return _normalize_sandbox_dependencies(
            dependencies, __version__, additional_features=[]
        )

    def _cleanup_sandbox(self) -> None:
        """Clean up sandbox directory."""
        import shutil

        if hasattr(self, "_sandbox_dir") and self._sandbox_dir:
            try:
                shutil.rmtree(self._sandbox_dir)
            except OSError:
                pass
            self._sandbox_dir = None


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
