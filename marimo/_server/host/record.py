# Copyright 2026 Marimo. All rights reserved.
"""Host discovery records with the API URL, token, and process identity."""

from __future__ import annotations

import atexit
import os
import re
import stat
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from ipaddress import IPv6Address, ip_address
from threading import Thread
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import uuid4

import msgspec

from marimo import _loggers
from marimo._core import protocol
from marimo._server.host import HOST_API_PATH, record_lock
from marimo._utils.xdg import marimo_state_dir

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from typing import BinaryIO

LOGGER = _loggers.marimo_logger()

_LOCKED_PREFIX = "marimo-flock-v1-"
_LOCKED_NAME = re.compile(rf"{_LOCKED_PREFIX}[0-9a-f]{{32}}\.json")


def discover_hosts(
    *, root: Path | None = None
) -> Iterator[protocol.HostRecord]:
    """Read private, loopback records belonging to live local processes.

    Invalid and stale records are skipped without deleting them. Discovery
    does not contact servers; a process can stop after its record is read.
    """
    import psutil

    directory = root if root is not None else marimo_state_dir() / "hosts-v1"
    try:
        original = directory.lstat()
        if not stat.S_ISDIR(original.st_mode) or not _private(original):
            return
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return
    for path in paths:
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
            )
            with os.fdopen(descriptor, "rb") as file:
                record = _read_private_record(file)
                if record is None:
                    continue
            current = directory.lstat()
            if (current.st_dev, current.st_ino) != (
                original.st_dev,
                original.st_ino,
            ) or not _private(current):
                return
            process = psutil.Process(record.process.pid)
            if (
                process.is_running()
                and process.status() != psutil.STATUS_ZOMBIE
                and abs(
                    process.create_time()
                    - record.process.started_at.timestamp()
                )
                < 1
            ):
                yield record
        except (
            OSError,
            ValueError,
            RecursionError,
            msgspec.DecodeError,
            psutil.Error,
        ):
            continue


def _read_private_record(file: BinaryIO) -> protocol.HostRecord | None:
    info = os.fstat(file.fileno())
    if not stat.S_ISREG(info.st_mode) or not _private(info):
        return None
    raw = file.read(65537)
    if len(raw) > 65536:
        return None
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
        return None
    return record


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
        self._path: Path | None = None
        self._lock: BinaryIO | None = None

    def write(self) -> None:
        """Publish atomically, locking the record on supported local filesystems."""
        if self._path is not None:
            return
        directory = marimo_state_dir() / "hosts-v1"
        directory.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(directory, 0o700)

        data = msgspec.json.format(msgspec.json.encode(self._record))
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        file = os.fdopen(fd, "wb")
        try:
            file.write(data)
            file.flush()
            if os.name == "posix":
                os.fchmod(fd, 0o600)
            device = record_lock.lock_local_record(fd)
            if device is None:
                file.close()  # Windows requires closing the file before rename.
                name = f"{uuid4()}.json"
            else:
                name = f"{_LOCKED_PREFIX}{uuid4().hex}.json"
            path = directory / name
            os.replace(tmp_path, path)
        except BaseException:
            with suppress(OSError):
                file.close()
            with suppress(OSError):
                os.unlink(tmp_path)
            raise

        self._lock = file if device is not None else None
        self._path = path
        atexit.register(self.remove)
        LOGGER.debug("Wrote host record %s", path)
        if device is not None:
            with suppress(RuntimeError):
                Thread(
                    target=_prune_abandoned,
                    args=(directory, device),
                    daemon=True,
                ).start()

    def remove(self) -> None:
        """Remove the record. Safe to call more than once."""
        if self._path is None or os.getpid() != self._record.process.pid:
            return
        try:
            self._path.unlink(missing_ok=True)
            LOGGER.debug("Removed host record %s", self._path)
        except OSError as e:
            LOGGER.warning(
                "Could not remove host record %s: %s", self._path, e
            )
        finally:
            self._path = None
            if self._lock is not None:
                self._lock.close()
                self._lock = None
            atexit.unregister(self.remove)


def _prune_abandoned(directory: Path, device: int) -> None:
    """Try once per marked record, on the same local device as the publisher."""
    with suppress(OSError):
        root = os.open(directory, os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(root)
            if info.st_dev != device or not _private(info):
                return
            for name in os.listdir(root):
                if _LOCKED_NAME.fullmatch(name):
                    with suppress(
                        OSError,
                        ValueError,
                        RecursionError,
                        msgspec.DecodeError,
                    ):
                        _prune_record(root, name, device)
        finally:
            os.close(root)


def _prune_record(root: int, name: str, device: int) -> None:
    fd = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root
    )
    try:
        info = os.fstat(fd)
        if (
            info.st_dev != device
            or not stat.S_ISREG(info.st_mode)
            or not _private(info)
        ):
            return
        if not record_lock.try_lock(fd):
            return
        with os.fdopen(fd, "rb", closefd=False) as file:
            if _read_private_record(file) is None:
                return
        entry = os.stat(name, dir_fd=root, follow_symlinks=False)
        if _private(entry) and os.path.samestat(info, entry):
            os.unlink(name, dir_fd=root)
    finally:
        os.close(fd)
