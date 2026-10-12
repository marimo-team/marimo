# Copyright 2026 Marimo. All rights reserved.
"""Host discovery records with the API URL, token, and process identity."""

from __future__ import annotations

import atexit
import os
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

import msgspec

from marimo import _loggers
from marimo._core import protocol
from marimo._server.host import HOST_API_PATH
from marimo._utils.xdg import marimo_state_dir

LOGGER = _loggers.marimo_logger()


def host_url(host: str, port: int, base_url: str) -> str:
    """Build a loopback URL for the host API."""
    loopback = "[::1]" if host.strip("[]") == "::1" else "127.0.0.1"
    return f"http://{loopback}:{port}{base_url}{HOST_API_PATH}"


def _process_started_at() -> datetime:
    try:
        import psutil

        started = psutil.Process(os.getpid()).create_time()
        return datetime.fromtimestamp(started, tz=timezone.utc)
    except Exception:
        # The fallback allows discovery but cannot verify process identity.
        return datetime.now(timezone.utc)


class HostRecordFile:
    """A discovery record written at startup and removed at shutdown."""

    def __init__(self, *, url: str, token: str) -> None:
        self._record = protocol.HostRecord(
            version=1,
            process=protocol.Process(
                pid=os.getpid(), started_at=_process_started_at()
            ),
            name="marimo",
            url=url,
            token=token,
        )
        self._path = marimo_state_dir() / "hosts-v1" / f"{uuid4()}.json"
        self._written = False

    def write(self) -> None:
        """Write atomically, with owner-only access on POSIX."""
        directory = self._path.parent
        directory.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(directory, 0o700)

        data = msgspec.json.format(msgspec.json.encode(self._record))
        fd, tmp_path = tempfile.mkstemp(dir=str(directory), suffix=".tmp")
        try:
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
            if os.name == "posix":
                os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        self._written = True
        atexit.register(self.remove)
        LOGGER.debug("Wrote host record %s", self._path)

    def remove(self) -> None:
        """Remove the record. Safe to call more than once."""
        if not self._written:
            return
        self._written = False
        try:
            self._path.unlink(missing_ok=True)
            LOGGER.debug("Removed host record %s", self._path)
        except OSError as e:
            LOGGER.warning(
                "Could not remove host record %s: %s", self._path, e
            )
