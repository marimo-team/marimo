# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Literal, Optional, Union, cast

from marimo import _loggers
from marimo._config.config import MarimoConfig
from marimo._config.manager import MarimoConfigReader
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import Alert
from marimo._server.utils import find_free_port
from marimo._tracer import server_tracer
from marimo._types.ids import CellId_t
from marimo._utils.formatter import DefaultFormatter, FormatError
from marimo._utils.paths import marimo_package_path

LOGGER = _loggers.marimo_logger()


class LspServer(ABC):
    port: int
    id: str

    @abstractmethod
    def start(self) -> Optional[Alert]:
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

    @server_tracer.start_as_current_span("lsp_server.start")
    def start(self) -> Optional[Alert]:
        if self.process is not None:
            LOGGER.debug("LSP server already started")
            return None

        validation_msg = self.validate_requirements()
        if validation_msg is not True:
            LOGGER.error(
                f"Cannot start {self.id} LSP server: {validation_msg}"
            )
            return self.missing_binary_alert()

        cmd = None
        try:
            LOGGER.debug("Starting LSP server at port %s...", self.port)
            cmd = self.get_command()

            # Empty command means the server is not enabled
            if not cmd:
                return None

            LOGGER.debug("... running command: %s", cmd)
            self.process = subprocess.Popen(
                cmd,
                # only show stdout when in development
                stdout=subprocess.PIPE
                if GLOBAL_SETTINGS.DEVELOPMENT_MODE
                else subprocess.DEVNULL,
                # subprocess.PIPE in Windows breaks the lsp-server
                stderr=subprocess.DEVNULL,
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
                # Process failed immediately
                stderr_output = (
                    self.process.stderr.read()
                    if self.process.stderr
                    else "No error output available"
                )
                LOGGER.error(
                    "LSP server failed to start with return code %s",
                    self.process.returncode,
                )
                LOGGER.error("Error output: %s", stderr_output)
                return Alert(
                    title="LSP server failed to start",
                    description="The LSP server failed to start. Please check the logs for more information.",
                    variant="danger",
                )

            LOGGER.debug("Started LSP server at port %s", self.port)

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
        return self.process.returncode is not None

    def stop(self) -> None:
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

    def missing_binary_alert(self) -> Alert:
        raise NotImplementedError()


class CopilotLspServer(BaseLspServer):
    id = "copilot"

    def validate_requirements(self) -> Union[str, Literal[True]]:
        if DependencyManager.which("node"):
            return True
        return (
            "node.js binary is missing. Install node at https://nodejs.org/."
        )

    def _lsp_bin(self) -> str:
        lsp_bin = marimo_package_path() / "_lsp" / "index.cjs"
        return str(lsp_bin)

    def get_command(self) -> list[str]:
        lsp_bin = self._lsp_bin()
        # Check if the LSP binary exists
        if not os.path.exists(lsp_bin):
            # Only debug since this may not exist in conda environments
            LOGGER.debug("LSP binary not found at %s", lsp_bin)
            return []
        return [
            "node",
            lsp_bin,
            "--port",
            str(self.port),
        ]

    def missing_binary_alert(self) -> Alert:
        return Alert(
            title="GitHub Copilot: Connection Error",
            description="<span><a class='hyperlink' href='https://docs.marimo.io/getting_started/index.html#github-copilot'>Install Node.js</a> to use copilot.</span>",
            variant="danger",
        )


class PyLspServer(BaseLspServer):
    id = "pylsp"

    def start(self) -> Optional[Alert]:
        # pylsp is not required, so we don't want to alert or fail if it is not installed
        if not DependencyManager.pylsp.has():
            LOGGER.debug("pylsp is not installed. Skipping LSP server.")
            return None
        return super().start()

    def validate_requirements(self) -> Union[str, Literal[True]]:
        if DependencyManager.pylsp.has():
            return True
        return "pylsp is missing. Install it with `pip install python-lsp-server`."

    def get_command(self) -> list[str]:
        import sys

        log_file = _loggers.get_log_directory() / "pylsp.log"

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
            str(log_file),
        ]

    def missing_binary_alert(self) -> Alert:
        return Alert(
            title="Python LSP: Connection Error",
            description="<span><a class='hyperlink' href='https://github.com/python-lsp/python-lsp-server'>Install python-lsp-server</a> for Python language support.</span>",
            variant="danger",
        )


class NoopLspServer(LspServer):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def is_running(self) -> bool:
        return False


class CompositeLspServer(LspServer):
    LANGUAGE_SERVERS = {
        "pylsp": PyLspServer,
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

    def _is_enabled(self, server_name: str) -> bool:
        # .get_config() is not cached
        config = self.config_reader.get_config()
        if server_name == "copilot":
            copilot = config["completion"]["copilot"]
            return copilot is True or copilot == "github"

        return cast(
            bool,
            cast(Any, config.get("language_servers", {}))
            .get(server_name, {})
            .get("enabled", False),
        )

    def start(self) -> Optional[Alert]:
        alerts: list[Alert] = []
        for server_name, server in self.servers.items():
            if not self._is_enabled(server_name):
                # We don't shut down the server if it is already running
                # in case the user wants to re-enable it
                continue
            # We call start again even for existing servers in case it failed
            # to start the first time (e.g. got new dependencies)
            alert = server.start()
            if alert is not None:
                alerts.append(alert)

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


if DependencyManager.pylsp.has():
    from pylsp import hookimpl

    formatter = DefaultFormatter(line_length=88)

    def format_signature(signature: str) -> str:
        try:
            signature_as_func = f"def {signature.strip()}:\n    pass"
            dummy_cell_id = cast(CellId_t, "")
            reformatted = formatter.format({dummy_cell_id: signature_as_func})[
                dummy_cell_id
            ]
            signature = reformatted.removeprefix("def ").removesuffix(
                ":\n    pass"
            )
        except (ModuleNotFoundError, FormatError):
            pass
        return "```python\n" + signature + "\n```\n"

    @hookimpl
    def pylsp_signatures_to_markdown(signatures: list[str]) -> str:
        return format_signature("\n".join(signatures))
