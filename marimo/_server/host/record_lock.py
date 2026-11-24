# Copyright 2026 Marimo. All rights reserved.
"""Lifetime locks for marimo's local discovery records."""

from __future__ import annotations

import os
import sys
from contextlib import suppress


def try_lock(fd: int) -> bool:
    """Hold an exclusive lock until the open file description is closed."""
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (ImportError, OSError):
        return False


def lock_local_record(fd: int) -> int | None:
    """Return the locked device, or publish a legacy record on other filesystems."""
    if os.name != "posix":
        return None
    try:
        device = os.fstat(fd).st_dev
        if _has_local_locks(device) and try_lock(fd):
            return device
    except Exception:
        # An unavailable mount table must not prevent host discovery.
        return None
    return None


def _has_local_locks(device: int) -> bool:
    # Network filesystems can grant locks that are visible only to one client.
    if sys.platform == "linux":
        number = f"{os.major(device)}:{os.minor(device)}"
        with open(
            "/proc/self/mountinfo", encoding="utf-8", errors="surrogateescape"
        ) as mounts:
            for line in mounts:
                mount, _, details = line.partition(" - ")
                if mount.split(maxsplit=3)[2] == number:
                    return details.split()[0] in {
                        "ext2",
                        "ext3",
                        "ext4",
                        "xfs",
                        "btrfs",
                        "tmpfs",
                        "zfs",
                    }
    elif sys.platform == "darwin":
        import psutil

        # APFS firmlinks can put a home directory on a different device than /.
        for mount in psutil.disk_partitions(all=True):
            if mount.fstype in {"apfs", "hfs"} and mount.device.startswith(
                "/dev/"
            ):
                with suppress(OSError):
                    if os.stat(mount.device).st_rdev == device:
                        return True
    return False
