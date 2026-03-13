# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from contextlib import AbstractContextManager
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from marimo import _loggers
from marimo._utils.net import find_free_port

LOGGER = _loggers.marimo_logger()

_LIVE_SERVER_START_TIMEOUT_S = 90.0
_LIVE_SERVER_POLL_INTERVAL_S = 0.2
_LIVE_SERVER_SHUTDOWN_TIMEOUT_S = 5.0
_LIVE_SERVER_DEFAULT_PORT = 2719


class LiveNotebookServer(AbstractContextManager["LiveNotebookServer"]):
    """Run a temporary headless marimo server for live output capture."""

    def __init__(self, *, filepath: str, argv: list[str] | None) -> None:
        self._filepath = filepath
        self._argv = list(argv or [])
        self._port = find_free_port(
            _LIVE_SERVER_DEFAULT_PORT,
            addr="127.0.0.1",
        )
        self._process: subprocess.Popen[str] | None = None
        self._log_file: tempfile._TemporaryFileWrapper[str] | None = None

    @property
    def page_url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def health_url(self) -> str:
        return f"{self.page_url}/health"

    def __enter__(self) -> LiveNotebookServer:
        """Start the server process and block until the health endpoint is ready."""

        self._log_file = tempfile.NamedTemporaryFile(
            mode="w+",
            encoding="utf-8",
            delete=False,
        )
        self._process = subprocess.Popen(
            self._build_command(),
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._wait_until_ready()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: object,
    ) -> None:
        """Terminate the server and clean up temporary log resources."""
        # Cleanup only. We intentionally do not suppress exceptions raised
        # inside the with-block.

        if self._process is not None:
            self._terminate_process(self._process)
            self._process = None

        if self._log_file is not None:
            log_name = self._log_file.name
            self._log_file.close()
            try:
                Path(log_name).unlink(missing_ok=True)
            except OSError:
                LOGGER.debug(
                    "Failed to clean up live capture server log file: %s",
                    log_name,
                )
            self._log_file = None

    def _build_command(self) -> list[str]:
        """Build the marimo CLI command used to launch the live notebook."""

        command = [
            sys.executable,
            "-m",
            "marimo",
            "run",
            self._filepath,
            "--headless",
            "--no-token",
            "--no-skew-protection",
            "--no-check",
            "--host",
            "127.0.0.1",
            "--port",
            str(self._port),
        ]
        if self._argv:
            command.extend(["--", *self._argv])
        return command

    def _wait_until_ready(self) -> None:
        """Poll process and health endpoint until server is ready or times out."""

        start = time.monotonic()
        while time.monotonic() - start < _LIVE_SERVER_START_TIMEOUT_S:
            process = self._process
            if process is None:
                raise RuntimeError("Live notebook server process is missing")
            if process.poll() is not None:
                logs = self._read_logs()
                raise RuntimeError(
                    "Live notebook server exited before becoming ready."
                    + (f"\n\n{logs}" if logs else "")
                )

            try:
                with urlopen(self.health_url, timeout=1) as response:
                    if response.status == 200:
                        return
            except URLError:
                pass

            time.sleep(_LIVE_SERVER_POLL_INTERVAL_S)

        logs = self._read_logs()
        raise RuntimeError(
            "Timed out waiting for live notebook server to become ready."
            + (f"\n\n{logs}" if logs else "")
        )

    def _read_logs(self) -> str:
        """Return recent process logs for startup/shutdown error reporting."""

        log_file = self._log_file
        if log_file is None:
            return ""
        log_file.flush()
        log_file.seek(0)
        logs = log_file.read()
        if len(logs) > 4_000:
            return logs[-4_000:]
        return logs

    def _terminate_process(self, process: subprocess.Popen[str]) -> None:
        """Gracefully terminate the server process and force-kill if needed."""

        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=_LIVE_SERVER_SHUTDOWN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=_LIVE_SERVER_SHUTDOWN_TIMEOUT_S)
