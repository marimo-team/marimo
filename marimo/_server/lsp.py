# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal, Optional, Union, cast

from marimo import _loggers
from marimo._config.config import MarimoConfig
from marimo._config.manager import MarimoConfigReader
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import AlertNotification
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


class BaseLspServer(LspServer):
    def __init__(self, port: int) -> None:
        self.port = port
        self.process: Optional[subprocess.Popen[str]] = None
        self._health_check_task: Optional[asyncio.Task[None]] = None
        self._startup_failed = False
        self.log_file = _loggers.get_log_directory() / f"{self.id}.log"

    @server_tracer.start_as_current_span("lsp_server.start")
    async def start(self) -> Optional[AlertNotification]:
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
            self.process.terminate()
            self.process = None
            LOGGER.debug("Stopped LSP server at port %s", self.port)
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
                if version_str.startswith("v"):
                    version_str = version_str[1:]  # Remove 'v' prefix

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


class NoopLspServer(LspServer):
    async def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def is_running(self) -> bool:
        return False


class CompositeLspServer(LspServer):
    LANGUAGE_SERVERS = {
        "pylsp": PyLspServer,
        "basedpyright": BasedpyrightServer,
        "ty": TyServer,
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


def any_lsp_server_running(config: MarimoConfig) -> bool:
    # Check if any language servers or copilot are enabled
    copilot_enabled = config["completion"]["copilot"]
    language_servers = config.get("language_servers", {})
    language_servers_enabled = any(
        cast(dict[str, Any], server).get("enabled", False)
        for server in language_servers.values()
    )
    return (copilot_enabled is not False) or language_servers_enabled
