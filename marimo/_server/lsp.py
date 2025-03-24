# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Literal, Optional, Union, cast

from marimo import _loggers
from marimo._config.config import CompletionConfig, LanguageServersConfig
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import Alert
from marimo._runtime.complete import _get_docstring
from marimo._server.utils import find_free_port
from marimo._tracer import server_tracer
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
        self.process: Optional[subprocess.Popen[bytes]] = None

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

            file_out = (
                None
                if GLOBAL_SETTINGS.DEVELOPMENT_MODE
                else subprocess.DEVNULL
            )
            LOGGER.debug("... running command: %s", cmd)
            self.process = subprocess.Popen(
                cmd,
                stdout=file_out,
                stderr=file_out,
                stdin=None,
            )
            LOGGER.debug(
                "... process return code (`None` means success): %s",
                self.process.returncode,
            )
            LOGGER.debug("Started LSP server at port %s", self.port)
        except Exception as e:
            LOGGER.error(
                "When starting language server (%s), got error: %s",
                cmd,
                e,
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
        lsp_bin = marimo_package_path() / "_lsp" / "index.js"
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

    def validate_requirements(self) -> Union[str, Literal[True]]:
        if DependencyManager.pylsp.has():
            return True
        return "pylsp is missing. Install it with `pip install python-lsp-server`."

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
    language_servers = {
        "pylsp": PyLspServer,
        "copilot": CopilotLspServer,
    }

    def __init__(
        self,
        lsp_config: LanguageServersConfig,
        completion_config: CompletionConfig,
        min_port: int,
    ) -> None:
        is_enabled: dict[str, bool] = {
            "copilot": (
                completion_config["copilot"] is True
                or completion_config["copilot"] == "github"
            ),
            **{
                server_name: cast(dict[str, bool], config)["enabled"]
                for server_name, config in lsp_config.items()
            },
        }
        self.servers: list[LspServer] = [
            constructor(find_free_port(min_port + 100 * i))
            for i, (server_name, constructor) in enumerate(
                self.language_servers.items()
            )
            if is_enabled.get(server_name, False)
        ]

    def start(self) -> None:
        for server in self.servers:
            server.start()

    def stop(self) -> None:
        for server in self.servers:
            server.stop()

    def is_running(self) -> bool:
        return any(server.is_running() for server in self.servers)


if DependencyManager.pylsp.has():
    from pylsp import hookimpl  # type: ignore[import-untyped,import-not-found]

    @hookimpl(tryfirst=True)  # type: ignore[misc]
    def pylsp_hover(
        config: Any, document: Any, position: dict[str, int]
    ) -> Optional[dict[str, Any]]:
        try:
            del config
            LOGGER.debug("Hovering over %s", document.path)
            import jedi  # type: ignore[import-untyped]

            # Use Jedi to get information about the symbol under cursor
            script = jedi.Script(document.source, path=document.path)

            definitions = script.goto(
                position["line"] + 1, position["character"]
            )

            if not definitions:
                return None

            definition = definitions[0]

            docstring = _get_docstring(definition)

            if not docstring:
                return None

            return {"contents": {"kind": "markdown", "value": docstring}}
        except Exception:
            return None

    @hookimpl()  # type: ignore[misc]
    def pylsp_completions(
        document: Any, position: dict[str, int]
    ) -> Optional[list[dict[str, Any]]]:
        del document
        del position
        return None
