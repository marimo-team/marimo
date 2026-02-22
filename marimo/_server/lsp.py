# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import socket
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal, Optional, Union, cast

from marimo import _loggers
from marimo._config.config import MarimoConfig
from marimo._config.manager import MarimoConfigReader
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import AlertNotification
from marimo._server.models.lsp import (
    LspHealthResponse,
    LspRestartResponse,
    LspServerHealth,
    LspServerId,
    LspServerStatus,
)
from marimo._tracer import server_tracer
from marimo._utils.net import find_free_port
from marimo._utils.paths import marimo_package_path
from marimo._utils.platform import is_windows

LOGGER = _loggers.marimo_logger()


class LspServer(ABC):
    port: int
    id: str

    @abstractmethod
    async def start(self) -> Optional[AlertNotification]:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def is_running(self) -> bool:
        pass

    @abstractmethod
    async def get_health(self) -> LspHealthResponse:
        pass

    @abstractmethod
    async def restart(
        self, server_ids: Optional[list[LspServerId]] = None
    ) -> LspRestartResponse:
        pass


class BaseLspServer(LspServer):
    def __init__(self, port: int) -> None:
        self.port = port
        self.process: Optional[subprocess.Popen[str]] = None
        self._health_check_task: Optional[asyncio.Task[None]] = None
        self._startup_failed = False
        self._started_at: Optional[float] = None  # Unix timestamp
        self._start_lock = asyncio.Lock()
        self.log_file = _loggers.get_log_directory() / f"{self.id}.log"

    @server_tracer.start_as_current_span("lsp_server.start")
    async def start(self) -> Optional[AlertNotification]:
        # Use lock to prevent race conditions when start() is called concurrently
        # (e.g., user rapidly toggles LSP settings)
        async with self._start_lock:
            return await self._start_internal()

    async def _start_internal(self) -> Optional[AlertNotification]:
        if self.process is not None:
            LOGGER.debug("LSP server already started")
            return None

        # Validation could be expensive, so we run it in a thread
        validation_msg = await asyncio.to_thread(self.validate_requirements)
        if validation_msg is not True:
            LOGGER.error(
                f"Cannot start {self.id} LSP server: {validation_msg}"
            )
            return self.missing_binary_alert()

        cmd = None
        try:
            LOGGER.info(f"Starting LSP {self.id} at port {self.port}")
            cmd = self.get_command()

            # Empty command means the server is not enabled
            if not cmd:
                return None

            LOGGER.debug("... running command: %s", cmd)
            self.process = subprocess.Popen(  # noqa: ASYNC220
                cmd,
                # only show stdout when in development
                stdout=subprocess.PIPE
                if GLOBAL_SETTINGS.DEVELOPMENT_MODE
                else subprocess.DEVNULL,
                # Capture stderr to diagnose startup failures
                # but subprocess.PIPE in Windows breaks the lsp-server
                stderr=subprocess.DEVNULL if is_windows() else subprocess.PIPE,
                stdin=None,
                text=True,
            )

            LOGGER.debug(
                "... process return code (`None` means still running): %s",
                self.process.returncode,
            )

            if (
                self.process.returncode is not None
                and self.process.returncode != 0
            ):
                # Process failed immediately - read stderr to diagnose
                stderr_output = (
                    self.process.stderr.read()
                    if self.process.stderr
                    else "No error output available"
                )
                LOGGER.error(
                    f"{self.id} LSP server failed to start with return code {self.process.returncode}"
                )
                LOGGER.error(f"Command: {' '.join(cmd)}")
                LOGGER.error(f"Error output: {stderr_output}")

                return AlertNotification(
                    title=f"{self.id} LSP server failed to start",
                    description=f"The {self.id} server crashed on startup. Check {self.log_file} for details. Error: {stderr_output[:200]}",
                    variant="danger",
                )

            LOGGER.info(f"Started LSP {self.id} at port {self.port}")
            self._started_at = time.time()

            # Start health monitoring in background
            if (
                self._health_check_task is None
                or self._health_check_task.done()
            ):
                self._health_check_task = asyncio.create_task(
                    self._monitor_process_health()
                )

        except Exception as e:
            cmd_str = " ".join(cmd or [])
            LOGGER.error(
                f"Failed to start {self.id} language server ({cmd_str}), got error: {e}",
            )
            self.process = None

        return None

    def is_running(self) -> bool:
        if self.process is None:
            return False
        # check if the process is still running
        self.process.poll()
        # returncode is None when process is running, set when it exits
        return self.process.returncode is None

    def has_failed(self) -> bool:
        """Check if the LSP server has failed to start or crashed."""
        return self._startup_failed or (
            self.process is not None
            and self.process.returncode is not None
            and self.process.returncode != 0
        )

    async def ping(
        self, timeout_ms: float = 5000
    ) -> tuple[bool, Optional[float]]:
        """
        Send an active health ping to verify server responsiveness.

        Returns (is_responsive, response_time_ms).
        Uses TCP socket connection check to verify the server port is listening.
        """
        if not self.is_running():
            return False, None

        start = time.monotonic()
        try:
            # Run socket connection in thread to avoid blocking
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self._tcp_ping, timeout_ms
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            return result, elapsed_ms if result else None
        except Exception:
            return False, None

    def _tcp_ping(self, timeout_ms: float) -> bool:
        """Attempt TCP connection to check if server is listening."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_ms / 1000)
            result = sock.connect_ex(("localhost", self.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def restart_server(self) -> Optional[AlertNotification]:
        """Stop and restart this LSP server."""
        self._startup_failed = False
        self._started_at = None
        self.stop()
        await asyncio.sleep(0.5)  # Brief delay for cleanup
        return await self.start()

    def _get_status(self) -> LspServerStatus:
        """Determine the current status of the server."""
        if self.has_failed():
            return "crashed"
        if not self.is_running():
            return "stopped"
        # Process is running - will need to check responsiveness externally
        return "running"

    async def get_health(self) -> LspHealthResponse:
        """Get health status of this single LSP server."""
        is_running = self.is_running()

        # Determine server status
        server_status: LspServerStatus
        last_ping_ms: Optional[float] = None

        if self.has_failed():
            server_status = "crashed"
        elif not is_running:
            server_status = "stopped"
        else:
            # Process is running - check responsiveness
            is_responsive, last_ping_ms = await self.ping()
            server_status = "running" if is_responsive else "unresponsive"

        server_health = LspServerHealth(
            server_id=LspServerId(self.id),
            status=server_status,
            port=self.port,
            last_ping_ms=last_ping_ms,
            started_at=self._started_at,
        )

        status: Literal["healthy", "degraded", "unhealthy"]
        if server_status == "running":
            status = "healthy"
        else:
            status = "unhealthy"

        return LspHealthResponse(status=status, servers=[server_health])

    async def restart(
        self, server_ids: Optional[list[LspServerId]] = None
    ) -> LspRestartResponse:
        """Restart this LSP server if requested."""
        sid = LspServerId(self.id)
        # If server_ids specified and this server not in list, skip
        if server_ids is not None and self.id not in server_ids:
            return LspRestartResponse(success=True, restarted=[], errors={})

        try:
            alert = await self.restart_server()
            if alert:
                return LspRestartResponse(
                    success=False,
                    restarted=[],
                    errors={sid: alert.description},
                )
            return LspRestartResponse(success=True, restarted=[sid], errors={})
        except Exception as e:
            return LspRestartResponse(
                success=False, restarted=[], errors={sid: str(e)}
            )

    async def _monitor_process_health(self) -> None:
        """Monitor the LSP process health and log if it crashes."""
        if self.process is None:
            return

        try:
            # Wait a bit to let the process fully initialize
            await asyncio.sleep(2)

            # Wait for the process to exit (non-blocking via executor)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.process.wait)

            # Process has exited - check if it was expected
            if self.process and self.process.returncode is not None:
                stderr_output = ""
                if self.process.stderr:
                    try:
                        # Try to read any remaining stderr
                        # Note: stderr might be empty if already consumed during wait()
                        stderr_output = self.process.stderr.read()
                    except Exception:
                        pass

                LOGGER.error(
                    f"{self.id} LSP server crashed unexpectedly with exit code {self.process.returncode}. Check {self.log_file} for details."
                )
                if stderr_output:
                    LOGGER.error(f"stderr: {stderr_output}")

                self._startup_failed = True

        except asyncio.CancelledError:
            # Task was cancelled, this is normal during shutdown
            # Re-raise to properly complete the cancellation
            raise
        except Exception as e:
            LOGGER.error(f"Error monitoring {self.id} LSP health: {e}")

    def stop(self) -> None:
        # Cancel health monitoring task
        if (
            self._health_check_task is not None
            and not self._health_check_task.done()
        ):
            self._health_check_task.cancel()

        if self.process is not None:
            LOGGER.debug("Stopping LSP server at port %s", self.port)
            self.process.terminate()
            try:
                # Wait for graceful shutdown with timeout
                self.process.wait(timeout=5)
                LOGGER.debug("LSP server stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if process doesn't respond to terminate
                LOGGER.warning(
                    "LSP server did not stop gracefully, forcing kill"
                )
                self.process.kill()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    LOGGER.error("Failed to kill LSP server process")
            self.process = None
        else:
            LOGGER.debug("LSP server not running")

    def validate_requirements(self) -> Union[str, Literal[True]]:
        raise NotImplementedError()

    def get_command(self) -> list[str]:
        raise NotImplementedError()

    def missing_binary_alert(self) -> AlertNotification:
        raise NotImplementedError()


class CopilotLspServer(BaseLspServer):
    id = "copilot"

    def __init__(self, port: int) -> None:
        super().__init__(port)
        self.log_file = _loggers.get_log_directory() / "github-copilot-lsp.log"

    def validate_requirements(self) -> Union[str, Literal[True]]:
        if not DependencyManager.which("node"):
            return "node.js binary is missing. Install node at https://nodejs.org/."

        # Check Node.js version
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version_str = result.stdout.strip()
                version_str = version_str.removeprefix(
                    "v"
                )  # Remove 'v' prefix

                # Parse major version
                major_version = int(version_str.split(".")[0])
                if major_version < 20:
                    return (
                        f"Node.js version {version_str} is too old. "
                        "GitHub Copilot requires Node.js version 20 or higher. "
                        "Please upgrade at https://nodejs.org/."
                    )
            else:
                # Fail open: If the node version check fails we don't want to not start the server.
                # If it fails again, the user will be alerted again.
                LOGGER.info(
                    "Failed to get Node.js version, stderr: %s", result.stderr
                )
        except Exception as e:
            # Fail open: If the node version check fails we don't want to not start the server.
            # If it fails again, the user will be alerted again.
            LOGGER.info("Failed to check Node.js version: %s", e)

        return True

    def _lsp_dir(self) -> Path:
        lsp_dir = marimo_package_path() / "_lsp"
        return Path(lsp_dir)

    def _lsp_bin(self) -> Path:
        return self._lsp_dir() / "index.cjs"

    def get_command(self) -> list[str]:
        lsp_bin = self._lsp_bin()
        # Check if the LSP binary exists
        if not lsp_bin.exists():
            # Only debug since this may not exist in conda environments
            LOGGER.debug("LSP binary not found at %s", lsp_bin)
            return []

        copilot_bin = self._lsp_dir() / "copilot" / "language-server.cjs"

        # Use typed format to avoid quoting issues: copilot:<binary_path>
        copilot_command = f"copilot:{copilot_bin}"

        return [
            "node",
            str(lsp_bin),
            "--port",
            str(self.port),
            "--lsp",
            copilot_command,
            "--log-file",
            str(self.log_file),
        ]

    def missing_binary_alert(self) -> AlertNotification:
        return AlertNotification(
            title="GitHub Copilot: Connection Error",
            description="<span><a class='hyperlink' href='https://docs.marimo.io/getting_started/index.html#github-copilot'>Install Node.js</a> to use copilot.</span>",
            variant="danger",
        )


class PyLspServer(BaseLspServer):
    """Python Language Server Protocol implementation using python-lsp-server (pylsp).

    Common issues and solutions:
    - If pylsp fails to start, check ~/.cache/marimo/logs/pylsp.log for errors
    - Version conflicts between jedi and python-lsp-server can cause failures
    - If autocomplete doesn't work, try disabling pylsp in Settings > Editor > Language Servers
    - When pylsp is disabled, marimo falls back to Jedi for completions
    """

    id = "pylsp"

    async def start(self) -> Optional[AlertNotification]:
        # pylsp is not required, so we don't want to alert or fail if it is not installed
        if not DependencyManager.pylsp.has():
            LOGGER.info(
                "pylsp is not installed. Skipping LSP server. Install with: pip install python-lsp-server"
            )
            return None
        return await super().start()

    def validate_requirements(self) -> Union[str, Literal[True]]:
        if not DependencyManager.pylsp.has():
            return "pylsp is missing. Install it with `pip install python-lsp-server`."

        # Try actually running pylsp to validate it works
        import sys

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pylsp", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return f"pylsp is installed but failed to run: {error_msg}. Check for dependency conflicts (e.g., jedi version compatibility)."
            return True
        except subprocess.TimeoutExpired:
            return "pylsp command timed out. The server may be unresponsive."
        except Exception as e:
            return f"Failed to validate pylsp: {e}"

    def get_command(self) -> list[str]:
        import sys

        return [
            sys.executable,
            "-m",
            "pylsp",
            "--ws",
            "-v",
            "--port",
            str(self.port),
            "--check-parent-process",
            "--log-file",
            str(self.log_file),
        ]

    def missing_binary_alert(self) -> AlertNotification:
        return AlertNotification(
            title="Python LSP: Connection Error",
            description=f"<span><a class='hyperlink' href='https://github.com/python-lsp/python-lsp-server'>Install python-lsp-server</a> for Python language support. If already installed, check {self.log_file} or disable pylsp in Settings > Editor > Language Servers.</span>",
            variant="danger",
        )


class BasedpyrightServer(BaseLspServer):
    id = "basedpyright"

    def __init__(self, port: int) -> None:
        super().__init__(port)
        self.log_file = _loggers.get_log_directory() / "basedpyright-lsp.log"

    async def start(self) -> Optional[AlertNotification]:
        # basedpyright is not required, so we don't want to alert or fail if it is not installed
        if not DependencyManager.basedpyright.has():
            LOGGER.debug("basedpyright is not installed. Skipping LSP server.")
            return None
        return await super().start()

    def validate_requirements(self) -> Union[str, Literal[True]]:
        if not DependencyManager.basedpyright.has():
            return "basedpyright is missing. Install it with `pip install basedpyright`."

        if not DependencyManager.which("node"):
            return "node.js binary is missing. Install node at https://nodejs.org/."

        return True

    def get_command(self) -> list[str]:
        lsp_bin = marimo_package_path() / "_lsp" / "index.cjs"

        return [
            "node",
            str(lsp_bin),
            "--port",
            str(self.port),
            "--lsp",
            "basedpyright:basedpyright-langserver",
            "--log-file",
            str(self.log_file),
        ]

    def missing_binary_alert(self) -> AlertNotification:
        return AlertNotification(
            title="basedpyright: Connection Error",
            description="<span><a class='hyperlink' href='https://docs.basedpyright.com'>Install basedpyright</a> for type checking support.</span>",
            variant="danger",
        )


class TyServer(BaseLspServer):
    id = "ty"

    def __init__(self, port: int) -> None:
        super().__init__(port)
        self.log_file = _loggers.get_log_directory() / "ty-lsp.log"

    async def start(self) -> Optional[AlertNotification]:
        # ty is not required, so we don't want to alert or fail if it is not installed
        if not DependencyManager.ty.has():
            LOGGER.debug("ty is not installed. Skipping LSP server.")
            return None
        return await super().start()

    def validate_requirements(self) -> Union[str, Literal[True]]:
        if not DependencyManager.ty.has():
            return "ty is missing. Install it with `pip install ty`."

        if not DependencyManager.which("node"):
            return "node.js binary is missing. Install node at https://nodejs.org/."

        return True

    def get_command(self) -> list[str]:
        from ty.__main__ import find_ty_bin  # type: ignore

        lsp_bin = marimo_package_path() / "_lsp" / "index.cjs"

        # Use typed format to avoid quoting issues: ty:<binary_path>
        ty_command = f"ty:{find_ty_bin()}"

        return [
            "node",
            str(lsp_bin),
            "--port",
            str(self.port),
            "--lsp",
            ty_command,
            "--log-file",
            str(self.log_file),
        ]

    def missing_binary_alert(self) -> AlertNotification:
        return AlertNotification(
            title="Ty: Connection Error",
            description="<span><a class='hyperlink' href='https://github.com/astral-sh/ty'>Install ty</a> for type checking support.</span>",
            variant="danger",
        )


class PyreflyServer(BaseLspServer):
    id = "pyrefly"

    def __init__(self, port: int) -> None:
        super().__init__(port)
        self.log_file = _loggers.get_log_directory() / "pyrefly-lsp.log"

    async def start(self) -> Optional[AlertNotification]:
        # Pyrefly is not required, so we don't want to alert or fail if it is not installed
        if not DependencyManager.pyrefly.has():
            LOGGER.debug("Pyrefly is not installed. Skipping LSP server.")
            return None
        return await super().start()

    def validate_requirements(self) -> Union[str, Literal[True]]:
        if not DependencyManager.pyrefly.has():
            return "Pyrefly is missing. Install it with `pip install pyrefly`."
        if not DependencyManager.which("node"):
            return "node.js binary is missing. Install node at https://nodejs.org/."
        return True

    def get_command(self) -> list[str]:
        from pyrefly.__main__ import get_pyrefly_bin  # type: ignore

        lsp_bin = marimo_package_path() / "_lsp" / "index.cjs"
        pyrefly_command = f"pyrefly:{get_pyrefly_bin()}"
        return [
            "node",
            str(lsp_bin),
            "--port",
            str(self.port),
            "--lsp",
            pyrefly_command,
            "--log-file",
            str(self.log_file),
        ]

    def missing_binary_alert(self) -> AlertNotification:
        return AlertNotification(
            title="Pyrefly: Connection Error",
            description="<span><a class='hyperlink' href='https://github.com/facebook/pyrefly'>Install pyrefly</a> for type checking support.</span>",
            variant="danger",
        )


class NoopLspServer(LspServer):
    port: int = 0
    id: str = "noop"

    async def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def is_running(self) -> bool:
        return False

    async def get_health(self) -> LspHealthResponse:
        return LspHealthResponse(status="healthy", servers=[])

    async def restart(
        self, server_ids: Optional[list[LspServerId]] = None
    ) -> LspRestartResponse:
        del server_ids  # Unused
        return LspRestartResponse(success=True, restarted=[], errors={})


class CompositeLspServer(LspServer):
    LANGUAGE_SERVERS = {
        "pylsp": PyLspServer,
        "basedpyright": BasedpyrightServer,
        "ty": TyServer,
        "pyrefly": PyreflyServer,
        "copilot": CopilotLspServer,
    }

    def __init__(
        self,
        config_reader: MarimoConfigReader,
        min_port: int,
    ) -> None:
        self.config_reader = config_reader
        self.min_port = min_port

        last_free_port = find_free_port(min_port)

        # NOTE: we construct all servers up front regardless of whether they are enabled
        # in order to properly mount them as Starlette routes with their own ports
        # With 2 servers, this is OK, but if we want to support more, we should
        # lazily construct servers, routes, and ports.
        # We still lazily start servers as they are enabled.
        # We also need to ensure that the ports are unique
        self.servers: dict[str, LspServer] = {}
        for server_name, server_constructor in self.LANGUAGE_SERVERS.items():
            last_free_port = find_free_port(last_free_port + 1)
            self.servers[server_name] = server_constructor(last_free_port)

    def _is_enabled(self, config: MarimoConfig, server_name: str) -> bool:
        if server_name == "copilot":
            copilot = config["completion"]["copilot"]
            return copilot is True or copilot == "github"

        return cast(
            bool,
            cast(Any, config.get("language_servers", {}))
            .get(server_name, {})
            .get("enabled", False),
        )

    async def start(self) -> Optional[AlertNotification]:
        # .get_config() should not be cached, as it may be updated by the user
        config = self.config_reader.get_config()
        tasks: list[asyncio.Task[Optional[AlertNotification]]] = []

        for server_name, server in self.servers.items():
            if not self._is_enabled(config, server_name):
                # We don't shut down the server if it is already running
                # in case the user wants to re-enable it
                continue
            # We call start again even for existing servers in case it failed
            # to start the first time (e.g. got new dependencies)
            tasks.append(asyncio.create_task(server.start()))

        # Start all servers in parallel
        results = await asyncio.gather(*tasks)
        alerts = [alert for alert in results if alert is not None]
        return alerts[0] if alerts else None

    def stop(self) -> None:
        for server in self.servers.values():
            server.stop()

    def is_running(self) -> bool:
        return any(server.is_running() for server in self.servers.values())

    async def get_health(self) -> LspHealthResponse:
        """Get aggregated health status of all LSP servers."""
        config = self.config_reader.get_config()
        server_healths: list[LspServerHealth] = []

        for server_id, server in self.servers.items():
            if not self._is_enabled(config, server_id):
                continue

            is_running = server.is_running()

            # Determine server status
            server_status: LspServerStatus
            last_ping_ms: Optional[float] = None
            started_at: Optional[float] = None

            if isinstance(server, BaseLspServer):
                started_at = server._started_at
                if server.has_failed():
                    server_status = "crashed"
                elif not is_running:
                    server_status = "stopped"
                else:
                    # Process is running - check responsiveness
                    is_responsive, last_ping_ms = await server.ping()
                    server_status = (
                        "running" if is_responsive else "unresponsive"
                    )
            else:
                server_status = "running" if is_running else "stopped"

            server_healths.append(
                LspServerHealth(
                    server_id=LspServerId(server_id),
                    status=server_status,
                    port=server.port,
                    last_ping_ms=last_ping_ms,
                    started_at=started_at,
                )
            )

        # Determine aggregate status
        status: Literal["healthy", "degraded", "unhealthy"]
        if not server_healths:
            status = "healthy"  # No servers configured
        elif all(s.status == "running" for s in server_healths):
            status = "healthy"
        elif any(s.status == "running" for s in server_healths):
            status = "degraded"
        else:
            status = "unhealthy"

        return LspHealthResponse(status=status, servers=server_healths)

    async def restart(
        self, server_ids: Optional[list[LspServerId]] = None
    ) -> LspRestartResponse:
        """Restart specified or failed LSP servers."""
        config = self.config_reader.get_config()
        restarted: list[LspServerId] = []
        errors: dict[LspServerId, str] = {}

        servers_to_restart: list[LspServerId] = []
        if server_ids is None:
            # Restart all failed/non-responsive servers
            for server_id, server in self.servers.items():
                if not self._is_enabled(config, server_id):
                    continue
                if isinstance(server, BaseLspServer):
                    is_running = server.is_running()
                    if server.has_failed():
                        servers_to_restart.append(LspServerId(server_id))
                    elif is_running:
                        is_responsive, _ = await server.ping()
                        if not is_responsive:
                            servers_to_restart.append(LspServerId(server_id))
        else:
            servers_to_restart = server_ids

        for server_id in servers_to_restart:
            sid = LspServerId(server_id)
            if server_id not in self.servers:
                errors[sid] = f"Unknown server: {server_id}"
                continue

            server = self.servers[server_id]
            if not isinstance(server, BaseLspServer):
                errors[sid] = "Server does not support restart"
                continue

            try:
                alert = await server.restart_server()
                if alert:
                    errors[sid] = alert.description
                else:
                    restarted.append(sid)
            except Exception as e:
                errors[sid] = str(e)

        return LspRestartResponse(
            success=len(errors) == 0,
            restarted=restarted,
            errors=errors,
        )


def any_lsp_server_running(config: MarimoConfig) -> bool:
    # Check if any language servers or copilot are enabled
    copilot_enabled = config["completion"]["copilot"]
    language_servers = config.get("language_servers", {})
    language_servers_enabled = any(
        cast(dict[str, Any], server).get("enabled", False)
        for server in language_servers.values()
    )
    return (copilot_enabled is not False) or language_servers_enabled
