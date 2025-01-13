from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Optional

from marimo import _loggers
from marimo._messaging.ops import (
    Alert,
)
from marimo._tracer import server_tracer
from marimo._utils.paths import import_files

LOGGER = _loggers.marimo_logger()


class LspServer(ABC):
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

        binpath = shutil.which(self.binary_name())
        if binpath is None:
            LOGGER.error(
                f"{self.binary_name()} not found; cannot start LSP server."
            )
            return self.missing_binary_alert()

        cmd = None
        try:
            LOGGER.debug("Starting LSP server at port %s...", self.port)
            cmd = self.get_command()
            if not cmd:
                return None
            LOGGER.debug("... running command: %s", cmd)
            # TODO: add logging when we are in -d mode
            self.process = subprocess.Popen(
                cmd.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
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
        return self.process is not None

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process = None
            LOGGER.debug("Stopped LSP server at port %s", self.port)
        else:
            LOGGER.debug("LSP server not running")

    def binary_name(self) -> str:
        raise NotImplementedError()

    def get_command(self) -> str:
        raise NotImplementedError()

    def missing_binary_alert(self) -> Alert:
        raise NotImplementedError()


class CopilotLspServer(BaseLspServer):
    def binary_name(self) -> str:
        return "node"

    def get_command(self) -> str:
        lsp_bin = os.path.join(
            str(import_files("marimo").joinpath("_lsp")),
            "index.js",
        )
        # Check if the LSP binary exists
        if not os.path.exists(lsp_bin):
            # Only debug since this may not exist in conda environments
            LOGGER.debug("LSP binary not found at %s", lsp_bin)
            return ""
        return f"node {lsp_bin} --port {self.port}"

    def missing_binary_alert(self) -> Alert:
        return Alert(
            title="GitHub Copilot: Connection Error",
            description="<span><a class='hyperlink' href='https://docs.marimo.io/getting_started/index.html#github-copilot'>Install Node.js</a> to use copilot.</span>",
            variant="danger",
        )


class PyLspServer(BaseLspServer):
    def binary_name(self) -> str:
        return "pylsp"

    def get_command(self) -> str:
        return f"pylsp --ws -v --port {self.port}"

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
    def __init__(self, servers: list[LspServer]) -> None:
        self.servers = servers

    def start(self) -> None:
        for server in self.servers:
            server.start()

    def stop(self) -> None:
        for server in self.servers:
            server.stop()

    def is_running(self) -> bool:
        return any(server.is_running() for server in self.servers)
