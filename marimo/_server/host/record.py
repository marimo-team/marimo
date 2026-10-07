# Copyright 2026 Marimo. All rights reserved.
"""The file that lets clients find this server.

A host writes `<state-dir>/hosts/<id>.json` while its API is served,
readable only by its owner. The record names the writing process, so a
stale one can be told from a live one, and carries the API's token.
"""

from __future__ import annotations

import atexit
import os
import tempfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import msgspec

from marimo import _loggers
from marimo._host import protocol
from marimo._server.host.context import HOST_API_PATH
from marimo._utils.xdg import marimo_state_dir

if TYPE_CHECKING:
    from pathlib import Path

LOGGER = _loggers.marimo_logger()

HOSTS_DIR = "hosts"


def hosts_dir() -> Path:
    """Where host records live for this user."""
    return marimo_state_dir() / HOSTS_DIR


def host_url(host: str, port: int, base_url: str) -> str:
    """Returns the API's URL, always at a loopback address."""
    loopback = "[::1]" if host.strip("[]") == "::1" else "127.0.0.1"
    return f"http://{loopback}:{port}{base_url}{HOST_API_PATH}"


def new_record(*, name: str, url: str, token: str) -> protocol.HostRecord:
    """Returns a version 1 record for this process."""
    return protocol.HostRecord(
        version=1,
        process=protocol.Process(
            pid=os.getpid(), started_at=_process_started_at()
        ),
        name=name,
        url=url,
        token=token,
    )


def _process_started_at() -> datetime:
    try:
        import psutil

        started = psutil.Process(os.getpid()).create_time()
        return datetime.fromtimestamp(started, tz=timezone.utc)
    except Exception:
        # Without the real start time a client cannot confirm the record
        # is ours; it will still find the API, and remove the record once
        # the pid is gone.
        return datetime.now(timezone.utc)


class HostRecordFile:
    """One record on disk, written at startup and removed at shutdown."""

    def __init__(
        self, record: protocol.HostRecord, directory: Path | None = None
    ) -> None:
        self.record = record
        self.path = (directory or hosts_dir()) / f"{uuid4()}.json"
        self._written = False

    def write(self) -> None:
        """Writes the record atomically, readable by this user only."""
        directory = self.path.parent
        directory.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(directory, 0o700)

        data = msgspec.json.format(msgspec.json.encode(self.record))
        fd, tmp_path = tempfile.mkstemp(dir=str(directory), suffix=".tmp")
        try:
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
            if os.name == "posix":
                os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        self._written = True
        atexit.register(self.remove)
        LOGGER.debug("Wrote host record %s", self.path)

    def remove(self) -> None:
        """Removes the record. Safe to call more than once."""
        if not self._written:
            return
        self._written = False
        try:
            self.path.unlink(missing_ok=True)
            LOGGER.debug("Removed host record %s", self.path)
        except OSError as e:
            LOGGER.warning("Could not remove host record %s: %s", self.path, e)
