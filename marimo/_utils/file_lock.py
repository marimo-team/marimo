# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import errno
import os
import stat
import sys
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@contextmanager
def file_lock(target: Path, *, blocking: bool) -> Iterator[None]:
    """Hold an OS lock on a persistent file.

    The lock file stays in place: unlinking it would let a new caller lock
    a different inode while existing callers still wait on the old one.
    Process exit releases the lock, including after a crash.
    """
    # Never truncate or follow a pre-existing link, even for the lock file.
    if target.is_symlink():
        raise OSError(f"Refusing to use symlink as lock file: {target}")
    descriptor = os.open(
        target, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    with os.fdopen(descriptor, "r+b", buffering=0) as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise OSError(f"Lock file is not a regular file: {target}")
        if sys.platform == "win32":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EDEADLK):
                        raise
                    if not blocking:
                        raise BlockingIOError from error
                    time.sleep(0.05)
            try:
                yield
            finally:
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB),
            )
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
