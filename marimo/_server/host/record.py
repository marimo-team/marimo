# Copyright 2026 Marimo. All rights reserved.
"""Host discovery records with the API URL, token, and process identity."""

from __future__ import annotations

import atexit
import os
import stat
import sys
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
from marimo._server.host import HOST_API_PATH
from marimo._utils.xdg import marimo_state_dir

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from typing import BinaryIO

LOGGER = _loggers.marimo_logger()

_LOCKED_PREFIX = "marimo-flock-v1-"
_LOCKED_RECORDS = _LOCKED_PREFIX + "[0-9a-f]" * 32 + ".json"


def discover_hosts(
    *, root: Path | None = None
) -> Iterator[protocol.HostRecord]:
    """Read private, loopback records belonging to live local processes.

    Invalid and stale records are skipped without deleting them. Discovery
    does not contact servers; a process can stop after its record is read.
    """
    import psutil

    directory = root if root is not None else marimo_state_dir() / "hosts-v1"
    for _, _, record in _read_records(directory):
        try:
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
        except (OSError, ValueError, psutil.Error):
            continue


def _read_records(
    directory: Path, pattern: str = "*.json"
) -> Iterator[tuple[Path, os.stat_result, protocol.HostRecord]]:
    try:
        original = directory.lstat()
        if not stat.S_ISDIR(original.st_mode) or not _private(original):
            return
        paths = sorted(directory.glob(pattern))
    except OSError:
        return
    for path in paths:
        try:
            with open(path, "rb", opener=_open_record) as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or not _private(info):
                    continue
                raw = file.read(65537)
                if len(raw) > 65536:
                    continue
                record = msgspec.json.decode(raw, type=protocol.HostRecord)
            current = directory.lstat()
            if (current.st_dev, current.st_ino) != (
                original.st_dev,
                original.st_ino,
            ) or not _private(current):
                return
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
            yield path, info, record
        except (OSError, ValueError, RecursionError, msgspec.DecodeError):
            continue


def _open_record(path: str, flags: int, *, dir_fd: int | None = None) -> int:
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    return os.open(path, flags, dir_fd=dir_fd)


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
            device = _lock_local_record(fd)
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


def _lock(fd: int) -> None:
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _lock_local_record(fd: int) -> int | None:
    """Only opt in on filesystems whose locks are local to this kernel."""
    # Mount inspection and locking are best effort.
    with suppress(Exception):
        device = os.fstat(fd).st_dev
        if _supports_local_locks(device):
            _lock(fd)
            return device
    return None


def _supports_local_locks(device: int) -> bool:
    if sys.platform == "linux":
        number = f"{os.major(device)}:{os.minor(device)}".encode()
        with open("/proc/self/mountinfo", "rb") as mounts:
            for mount in mounts:
                if mount.split(maxsplit=3)[2] == number:
                    fstype = mount.partition(b" - ")[2].split(maxsplit=1)[0]
                    return fstype in {
                        b"ext2",
                        b"ext3",
                        b"ext4",
                        b"xfs",
                        b"btrfs",
                        b"tmpfs",
                        b"zfs",
                    }
    elif sys.platform == "darwin":
        import psutil

        # Match the device since APFS firmlinks can cross mounts.
        for mount in psutil.disk_partitions(all=True):
            if mount.fstype in {"apfs", "hfs"} and mount.device.startswith(
                "/dev/"
            ):
                with suppress(OSError):
                    if os.stat(mount.device).st_rdev == device:
                        return True
    return False


def _prune_abandoned(directory: Path, device: int) -> None:
    """Try once per marked record, on the same local device as the publisher."""
    with suppress(OSError):
        root = os.open(directory, os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(root)
            if info.st_dev != device or not _private(info):
                return
            for path, candidate, _ in _read_records(
                directory, _LOCKED_RECORDS
            ):
                if candidate.st_dev == device:
                    with suppress(OSError):
                        _unlink_if_unlocked(root, path.name, candidate)
        finally:
            os.close(root)


def _unlink_if_unlocked(
    root: int, name: str, candidate: os.stat_result
) -> None:
    fd = _open_record(name, os.O_RDONLY, dir_fd=root)
    try:
        if os.path.samestat(candidate, os.fstat(fd)):
            _lock(fd)
            entry = os.stat(name, dir_fd=root, follow_symlinks=False)
            if (
                _private(entry)
                and os.path.samestat(candidate, entry)
                and candidate.st_ctime_ns == entry.st_ctime_ns
            ):
                os.unlink(name, dir_fd=root)
    finally:
        os.close(fd)
