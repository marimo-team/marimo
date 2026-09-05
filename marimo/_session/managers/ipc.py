# Copyright 2026 Marimo. All rights reserved.
"""IPC-based managers using ZeroMQ.

These implementations launch the kernel as a subprocess and communicate
via ZeroMQ channels. Each notebook gets its own sandboxed virtual environment.
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from marimo import _loggers
from marimo._config.config import VenvConfig
from marimo._config.manager import MarimoConfigReader
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._environments.environment import (
    Environment,
    launch,
    launch_isolated,
    sync_notebook,
)
from marimo._environments.overlay import runtime_overlay
from marimo._environments.uv import UvError, UvMissingScriptMetadataError
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session._venv import (
    check_python_version_compatibility,
    get_configured_venv_python,
    get_kernel_pythonpath,
    has_marimo_installed,
    install_marimo_into_venv,
)
from marimo._session.model import SessionMode
from marimo._session.queue import ProcessLike, QueueType, route_control_request
from marimo._session.types import KernelManager, QueueManager
from marimo._utils.subprocess import (
    interrupt_kernel_process,
    try_kill_process_and_group,
)
from marimo._utils.typed_connection import TypedConnection

if TYPE_CHECKING:
    from marimo._ast.cell import CellConfig
    from marimo._ipc.queue_manager import QueueManager as IPCQueueManagerType
    from marimo._ipc.types import ConnectionInfo
    from marimo._runtime.commands import AppMetadata
    from marimo._runtime.virtual_file.storage import VirtualFileStorageType
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def _get_venv_config(config_manager: MarimoConfigReader) -> VenvConfig:
    """Get the [tool.marimo.venv] config from a config manager."""
    config = config_manager.get_config(hide_secrets=False)
    return cast(VenvConfig, config.get("venv", {}))


# How long close_kernel waits for the kernel to dump its profile, and
# for a graceful exit, before killing it. Bounded: the live server
# closes sessions on the event loop, which must not stall indefinitely.
PROFILE_FLUSH_TIMEOUT: float = 10.0
GRACEFUL_EXIT_TIMEOUT: float = 5.0

# How long start_kernel waits for KERNEL_READY. Generous by default: a
# cold uv resolution of the notebook's environment can take minutes.
KERNEL_STARTUP_TIMEOUT: float = 600.0


def _startup_timeout() -> float:
    raw = os.environ.get("MARIMO_KERNEL_STARTUP_TIMEOUT")
    if raw:
        try:
            return float(raw)
        except ValueError:
            LOGGER.warning(
                "Ignoring invalid MARIMO_KERNEL_STARTUP_TIMEOUT: %s", raw
            )
    return KERNEL_STARTUP_TIMEOUT


def _profile_path_for(filename: str | None) -> str | None:
    """Where this kernel dumps profile statistics, if profiling is on."""
    profile_dir = GLOBAL_SETTINGS.PROFILE_DIR
    if profile_dir is None:
        return None
    basename = (
        os.path.basename(filename) + str(uuid4())
        if filename is not None
        else str(uuid4())
    )
    return os.path.join(profile_dir, basename)


def _virtual_file_storage() -> VirtualFileStorageType | None:
    """Storage for the kernel's virtual files.

    Shared memory, so the server's /@file endpoint can read buffers the
    kernel subprocess wrote. `marimo run` does not preflight shared
    memory the way `marimo edit` does, so fall back to None (inline data
    URLs) where it is unavailable rather than failing kernel startup.
    """
    from marimo._utils.platform import check_shared_memory_available

    available, _ = check_shared_memory_available()
    return "shared_memory" if available else None


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
    ) -> QueueType[commands.BatchableCommand]:
        return self._ipc.set_ui_element_queue

    @property
    def completion_queue(  # type: ignore[override]
        self,
    ) -> QueueType[commands.OutOfBandCommand]:
        return self._ipc.completion_queue

    @property
    def input_queue(  # type: ignore[override]
        self,
    ) -> QueueType[str]:
        return self._ipc.input_queue

    @property
    def stream_queue(  # type: ignore[override]
        self,
    ) -> QueueType[KernelMessage | None]:
        return cast(
            QueueType[KernelMessage | None],
            self._ipc.stream_queue,
        )

    @property
    def win32_interrupt_queue(  # type: ignore[override]
        self,
    ) -> QueueType[bool] | None:
        return self._ipc.win32_interrupt_queue

    def close_queues(self) -> None:
        self._ipc.close_queues()

    def put_control_request(self, request: commands.CommandMessage) -> None:
        route_control_request(
            request,
            self.control_queue,
            self.completion_queue,
            self.set_ui_element_queue,
        )

    def put_input(self, text: str) -> None:
        self.input_queue.put(text)


def _decode_tail(tail: deque[bytes]) -> str:
    return b"".join(tail).decode(errors="replace")


def _parse_kernel_info(line: str) -> tuple[int | None, str | None]:
    """Parses the optional `KERNEL_INFO <pid> <executable>` line.

    Tolerates absence and shorter forms for version skew with kernels
    that predate the line.
    """
    parts = line.split(" ", 2)
    if len(parts) < 2 or parts[0] != "KERNEL_INFO":
        return None, None
    try:
        pid = int(parts[1])
    except ValueError:
        return None, None
    executable = parts[2] if len(parts) > 2 and parts[2] else None
    return pid, executable


def construct_kernel_env(
    base_env: dict[str, str],
    venv_python: str,
    *,
    is_ephemeral_sandbox: bool,
    writable: bool,
    kernel_pythonpath: str | None = None,
) -> dict[str, str]:
    """Build environment variables for a kernel subprocess.

    Args:
        base_env: Starting environment (typically `os.environ.copy()`).
        venv_python: Path to the Python executable in the target venv.
        is_ephemeral_sandbox: Whether the kernel runs in a sandbox venv
            rather than a configured one.
        writable: Whether the kernel venv supports package installs.
        kernel_pythonpath: Extra PYTHONPATH entries for read-only
            configured venvs that don't have marimo installed.

    Returns:
        A **new** dict with the appropriate overrides applied.
    """
    env = dict(base_env)

    # Sandbox identity is per-kernel, not inherited: a configured venv
    # kernel inside a sandboxed server must not route package changes
    # through a script environment it does not run in.
    env.pop("MARIMO_SANDBOX_MODE", None)
    env.pop("MARIMO_MANAGE_SCRIPT_METADATA", None)

    if kernel_pythonpath is not None:
        existing = env.get("PYTHONPATH", "")
        if existing:
            env["PYTHONPATH"] = f"{kernel_pythonpath}{os.pathsep}{existing}"
        else:
            env["PYTHONPATH"] = kernel_pythonpath

    if is_ephemeral_sandbox:
        # Override UV env vars so the kernel subprocess sees the sandbox
        # venv as its environment, not the outer uv project.
        env["VIRTUAL_ENV"] = str(Path(venv_python).parent.parent)
        env.pop("UV_PROJECT_ENVIRONMENT", None)

    if writable:
        # Setting this attempts to make auto-installations work even if
        # other normally detected criteria are not true.
        # IPC by itself does not seem to trigger them.
        env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"

    return env


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
        redirect_console_to_browser: bool = True,
    ) -> None:
        self.queue_manager = queue_manager
        self.connection_info = connection_info
        self.mode = mode
        self.configs = configs
        self.app_metadata = app_metadata
        self.config_manager = config_manager
        self.redirect_console_to_browser = redirect_console_to_browser

        self._process: subprocess.Popen[bytes] | None = None
        self.kernel_task: ProcessLike | None = None
        self._venv_python: str | None = None
        self._profile_path = _profile_path_for(app_metadata.filename)
        self._script_environment: Environment | None = None
        # The kernel's own pid: a launcher such as uv may sit between the
        # manager and the kernel, so _process.pid is not the kernel.
        self._kernel_pid: int | None = None

    @property
    def script_environment(self) -> Environment | None:
        """The synchronized script environment the kernel runs in, if any."""
        return self._script_environment

    def start_kernel(self) -> None:
        from marimo._cli.print import echo, muted
        from marimo._ipc.types import KernelArgs

        kernel_args = KernelArgs(
            configs=self.configs,
            app_metadata=self.app_metadata,
            user_config=self.config_manager.get_config(hide_secrets=False),
            log_level=GLOBAL_SETTINGS.LOG_LEVEL,
            profile_path=self.profile_path,
            connection_info=self.connection_info,
            is_run_mode=self.mode == SessionMode.RUN,
            redirect_console_to_browser=self.redirect_console_to_browser,
            parent_pid=os.getpid(),
            virtual_file_storage=_virtual_file_storage(),
        )

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
        kernel_pythonpath: str | None = None

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
                kernel_pythonpath = get_kernel_pythonpath()
            # Store the venv python for package manager targeting
            self._venv_python = venv_python
            env = construct_kernel_env(
                base_env=os.environ.copy(),
                venv_python=venv_python,
                is_ephemeral_sandbox=False,
                writable=writable,
                kernel_pythonpath=kernel_pythonpath,
            )
            cmd: list[str] = [venv_python, "-m", "marimo._ipc.launch_kernel"]
            plan_launched = False
        else:
            # Synchronize the notebook's script environment; a notebook
            # without a metadata block runs ephemerally, and packages
            # installed during its session die with it.
            kernel_args_list = ["-m", "marimo._ipc.launch_kernel"]
            overlay = runtime_overlay()
            handle = None
            filename = self.app_metadata.filename
            if filename is not None:
                from marimo._environments import script_metadata

                # Best-effort: give metadata-less notebooks a block so
                # they get a real script environment instead of an
                # ephemeral one whose installs the server cannot target.
                try:
                    script_metadata.ensure_marimo(filename)
                except Exception as e:
                    LOGGER.warning(
                        "Failed to add marimo to script metadata: %s", e
                    )
                try:
                    handle = sync_notebook(
                        filename, on_output=lambda _line: None
                    )
                except UvMissingScriptMetadataError:
                    handle = None
                except UvError as e:
                    raise KernelStartupError(
                        f"Failed to build sandbox environment.\n\n{e}"
                    ) from e

            if handle is not None:
                self._venv_python = handle.python
                self._script_environment = handle
                plan = launch(
                    handle,
                    kernel_args_list,
                    overlay=overlay,
                    base_env=os.environ.copy(),
                )
                echo(
                    f"Running kernel in script environment: "
                    f"{muted(handle.root)}",
                    err=True,
                )
            else:
                import platform

                plan = launch_isolated(
                    kernel_args_list,
                    overlay=overlay,
                    python=platform.python_version(),
                    base_env=os.environ.copy(),
                )
                echo("Running kernel in an ephemeral sandbox", err=True)

            plan_launched = True
            env = plan.env
            # Ephemeral sandboxes are always writable; the kernel manages
            # the notebook's script metadata.
            env["MARIMO_MANAGE_SCRIPT_METADATA"] = "true"
            if handle is not None:
                # Only a kernel that runs in the script environment may
                # route package changes through it; an isolated kernel
                # installs into itself imperatively.
                env["MARIMO_SANDBOX_MODE"] = "multi"
            else:
                env.pop("MARIMO_SANDBOX_MODE", None)
            cmd = list(plan.argv)

        LOGGER.debug(f"Launching kernel: {' '.join(cmd)}")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=(
                    plan.start_new_session if plan_launched else False
                ),
            )

            # Drain the kernel's stderr from the very start: uv resolves
            # the overlay at launch time, and its output can fill the
            # pipe before the kernel ever prints KERNEL_READY,
            # deadlocking startup. Tee to the server's stderr as the
            # kernel's console, keeping a tail for startup diagnostics.
            stderr_pipe = self._process.stderr
            stderr_tail: deque[bytes] = deque(maxlen=64)

            def drain_stderr() -> None:
                assert stderr_pipe is not None
                for line in iter(stderr_pipe.readline, b""):
                    stderr_tail.append(line)
                    try:
                        sys.stderr.buffer.write(line)
                        sys.stderr.buffer.flush()
                    except Exception:
                        pass
                stderr_pipe.close()

            threading.Thread(target=drain_stderr, daemon=True).start()

            # Send connection info via stdin
            assert self._process.stdin is not None
            self._process.stdin.write(kernel_args.encode_json())
            self._process.stdin.flush()
            self._process.stdin.close()

            # Read the handshake on a thread so the wait can be bounded
            # and can notice a child that dies without printing it.
            # Plan-launched kernels run the overlay-pinned marimo, so
            # the KERNEL_INFO line is guaranteed; a configured venv may
            # run an older marimo that never prints it, and reading a
            # second line would hang its startup.
            stdout_pipe = self._process.stdout
            assert stdout_pipe is not None
            expected_lines = 2 if plan_launched else 1
            handshake: queue.Queue[str] = queue.Queue()

            def read_handshake() -> None:
                for _ in range(expected_lines):
                    line = stdout_pipe.readline()
                    if not line:
                        return
                    handshake.put(line.decode().strip())

            threading.Thread(target=read_handshake, daemon=True).start()

            deadline = time.monotonic() + _startup_timeout()
            ready = self._await_handshake_line(
                handshake, deadline, stderr_tail, cmd
            )
            if ready != "KERNEL_READY":
                raise KernelStartupError(
                    f"Kernel failed to start.\n\n"
                    f"Command: {' '.join(cmd)}\n\n"
                    f"Stderr:\n{_decode_tail(stderr_tail)}"
                )

            if plan_launched:
                info = self._await_handshake_line(
                    handshake, deadline, stderr_tail, cmd
                )
                kernel_pid, kernel_executable = _parse_kernel_info(info)
                self._kernel_pid = kernel_pid
                if self._venv_python is None and kernel_executable is not None:
                    # An ephemeral kernel's environment is only knowable
                    # from the kernel itself; the server package panel
                    # targets it.
                    self._venv_python = kernel_executable

            LOGGER.debug("Kernel ready")

            # Create a ProcessLike wrapper for the subprocess
            self.kernel_task = _SubprocessWrapper(self._process)
        except KernelStartupError:
            raise
        except Exception as e:
            # Wrap other exceptions as KernelStartupError
            raise KernelStartupError(
                f"Failed to start kernel subprocess.\n\n{e}"
            ) from e

    def _await_handshake_line(
        self,
        handshake: queue.Queue[str],
        deadline: float,
        stderr_tail: deque[bytes],
        cmd: list[str],
    ) -> str:
        """The next handshake line, bounded by exit and deadline.

        Raises `KernelStartupError` when the child exits without
        producing it or the deadline passes; a hung child is killed so
        an unresponsive launch cannot leak a process tree.
        """
        assert self._process is not None
        while True:
            try:
                return handshake.get(timeout=0.1)
            except queue.Empty:
                pass
            if self._process.poll() is not None:
                # The reader thread may still be flushing lines the
                # child printed just before exiting.
                try:
                    return handshake.get(timeout=0.5)
                except queue.Empty:
                    raise KernelStartupError(
                        f"Kernel exited during startup "
                        f"(exit code {self._process.returncode}).\n\n"
                        f"Command: {' '.join(cmd)}\n\n"
                        f"Stderr:\n{_decode_tail(stderr_tail)}"
                    ) from None
            if time.monotonic() > deadline:
                try:
                    try_kill_process_and_group(
                        _SubprocessWrapper(self._process)
                    )
                except Exception as e:
                    LOGGER.warning(e)
                raise KernelStartupError(
                    f"Kernel did not become ready within "
                    f"{_startup_timeout():.0f}s (override with "
                    f"MARIMO_KERNEL_STARTUP_TIMEOUT).\n\n"
                    f"Command: {' '.join(cmd)}\n\n"
                    f"Stderr:\n{_decode_tail(stderr_tail)}"
                )

    @property
    def pid(self) -> int | None:
        if self._process is None:
            return None
        return self._process.pid

    @property
    def profile_path(self) -> str | None:
        return self._profile_path

    @property
    def venv_python(self) -> str | None:
        """Python executable path for the kernel's venv."""
        return self._venv_python

    def is_alive(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    def interrupt_kernel(self) -> None:
        if self._process is None:
            return

        if self._process.pid is not None and self.is_alive():
            interrupt_kernel_process(
                self._kernel_pid or self._process.pid,
                self.queue_manager.win32_interrupt_queue,
            )

    def close_kernel(self, *, graceful: bool = False) -> None:
        if self._process is not None:
            self.queue_manager.put_control_request(
                commands.StopKernelCommand()
            )
            # A clean stop lets the kernel flush pending work (the
            # profile dump, cache writes) before we kill it. Unlike the
            # multiprocessing manager, every wait here is bounded.
            if self.profile_path is not None and self.is_alive():
                from marimo._cli.print import echo

                echo(
                    f"\tWriting profile statistics to {self.profile_path} ..."
                )
                # The kernel dumps stats just before exiting, so a
                # completed exit means a complete file. (The
                # multiprocessing manager polls for the file instead
                # because joining its Process hangs; subprocess.wait
                # has no such problem.)
                try:
                    self._process.wait(timeout=PROFILE_FLUSH_TIMEOUT)
                except subprocess.TimeoutExpired:
                    pass
            self.queue_manager.close_queues()
            if graceful and self._process.poll() is None:
                try:
                    self._process.wait(timeout=GRACEFUL_EXIT_TIMEOUT)
                except subprocess.TimeoutExpired:
                    pass
            if self._process.poll() is None and self.kernel_task is not None:
                # The kernel leads its own process group; kill it first
                # so user-code subprocesses die too, then the launcher.
                if self._kernel_pid is not None and sys.platform != "win32":
                    try:
                        os.killpg(os.getpgid(self._kernel_pid), signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):
                        pass
                try:
                    try_kill_process_and_group(self.kernel_task)
                except ProcessLookupError:
                    pass
                except Exception as e:
                    LOGGER.warning(e)

        # Always attempt cleanup, even if _process is None

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

    @property
    def exitcode(self) -> int | None:
        """Mirror multiprocessing.Process.exitcode for exit diagnostics."""
        return self._process.poll()

    def is_alive(self) -> bool:
        return self._process.poll() is None

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()

    def join(self, timeout: float | None = None) -> None:
        self._process.wait(timeout=timeout)
