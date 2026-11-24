# Copyright 2026 Marimo. All rights reserved.
"""Host discovery records with the API URL, token, and process identity."""

from __future__ import annotations

import atexit
import os
import stat
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from ipaddress import IPv6Address, ip_address
from threading import Thread
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit
from uuid import uuid4

import msgspec

from marimo import _loggers
from marimo._core import protocol
from marimo._server.host import HOST_API_PATH
from marimo._utils.xdg import marimo_state_dir

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

LOGGER = _loggers.marimo_logger()


def discover_hosts(
    *, root: Path | None = None
) -> Iterator[protocol.HostRecord]:
    """Read private, loopback records belonging to live local processes.

    Invalid and stale records are skipped without deleting them. Discovery
    does not contact servers; a process can stop after its record is read.
    """
    directory = root if root is not None else marimo_state_dir() / "hosts-v1"
    for _, record in _host_records(directory, state="live"):
        yield record


def _process_state(
    identity: protocol.Process,
) -> Literal["live", "stale", "unknown"]:
    if identity.started_at.tzinfo is None:
        return "unknown"
    try:
        import psutil
    except ImportError:
        return "unknown"

    try:
        process = psutil.Process(identity.pid)
        if process.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
            return "stale"
        start_delta = process.create_time() - identity.started_at.timestamp()
        if abs(start_delta) < 1 and process.is_running():
            return "live"
        # An older process may have recorded the fallback timestamp at startup.
        if start_delta >= 1:
            return "stale"
    except psutil.NoSuchProcess:
        return "stale"
    except (OSError, ValueError, OverflowError, psutil.Error):
        return "unknown"
    return "unknown"


def _host_records(
    directory: Path,
    *,
    state: Literal["live", "stale"],
    exclude: Path | None = None,
) -> Iterator[tuple[Path, protocol.HostRecord]]:
    try:
        original = directory.lstat()
        if not stat.S_ISDIR(original.st_mode) or not _private(original):
            return
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return
    for path in paths:
        if path == exclude:
            continue
        try:
            with open(path, "rb", opener=_open_record) as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or not _private(info):
                    continue
                raw = file.read(65537)
                if len(raw) > 65536:
                    continue
                record = msgspec.json.decode(raw, type=protocol.HostRecord)
            url = urlsplit(record.url)
            if (
                url.scheme != "http"
                or url.hostname is None
                or not ip_address(url.hostname).is_loopback
                or url.username is not None
                or url.password is not None
                or url.query
                or url.fragment
                or any(c.isspace() or c == "\\" for c in record.url)
                or url.port == 0
            ):
                continue
            if _process_state(record.process) != state:
                continue
            current = directory.lstat()
            if not (_private(current) and os.path.samestat(original, current)):
                return
            entry = path.lstat()
            if os.path.samestat(info, entry) and _private(entry):
                yield path, record
        except (OSError, ValueError, RecursionError, msgspec.DecodeError):
            continue


def _open_record(path: str, flags: int) -> int:
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    return os.open(path, flags)


def _private(info: os.stat_result) -> bool:
    return os.name != "posix" or (
        info.st_uid == os.getuid() and info.st_mode & 0o077 == 0
    )


def host_url(host: str, port: int, base_url: str) -> str | None:
    """Build the loopback URL for the host API.

    Returns None when the server binds an address that loopback cannot
    reach, because a record would then name a URL nobody can open.
    """
    name = host.strip("[]")
    if name.lower() == "localhost":
        loopback = "127.0.0.1"
    else:
        try:
            address = ip_address(name)
        except ValueError:
            return None
        if isinstance(address, IPv6Address) and address.ipv4_mapped:
            # Only Python 3.13 treats a mapped loopback as loopback.
            address = address.ipv4_mapped
        if address.is_unspecified:
            # A wildcard IPv6 bind is v6-only, so its loopback is ::1.
            loopback = "[::1]" if address.version == 6 else "127.0.0.1"
        elif address.is_loopback:
            # A socket bound to one loopback address refuses the others.
            loopback = f"[{address}]" if address.version == 6 else str(address)
        else:
            return None
    return f"http://{loopback}:{port}{base_url}{HOST_API_PATH}"


def _process_started_at() -> datetime:
    try:
        import psutil

        started = psutil.Process(os.getpid()).create_time()
        return datetime.fromtimestamp(started, tz=UTC)
    except Exception:
        # The fallback allows discovery but cannot verify process identity.
        return datetime.now(UTC)


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
        """Publish the record, then clean up abandoned records in the background."""
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
        with suppress(RuntimeError):
            Thread(target=self._prune_stale, daemon=True).start()

    def _prune_stale(self) -> None:
        # An open record can block its removal on Windows.
        for path, _ in _host_records(
            self._path.parent, state="stale", exclude=self._path
        ):
            with suppress(OSError):
                path.unlink()

    def remove(self) -> None:
        """Remove the record. Safe to call more than once."""
        if not self._written or os.getpid() != self._record.process.pid:
            return
        self._written = False
        try:
            self._path.unlink(missing_ok=True)
            LOGGER.debug("Removed host record %s", self._path)
        except OSError as e:
            LOGGER.warning(
                "Could not remove host record %s: %s", self._path, e
            )
