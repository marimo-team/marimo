# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from marimo._output.rich_help import mddoc
from marimo._runtime.watch._path import (
    WATCHER_SLEEP_INTERVAL,
    PathState,
    write_side_effect,
)

# For testing only - do not use in production
_TEST_SLEEP_INTERVAL: float | None = None


def watch_file(
    path: Path, state: FileState, should_exit: threading.Event
) -> None:
    """Watch a file for changes and update the state."""
    last_mtime: float = 0
    current_mtime = last_mtime
    sleep_interval = _TEST_SLEEP_INTERVAL or WATCHER_SLEEP_INTERVAL
    while not should_exit.is_set():
        time.sleep(sleep_interval)
        try:
            current_mtime = path.stat().st_mtime
        except FileNotFoundError:
            # File has been deleted, trigger a change
            current_mtime = 0
        except Exception as e:
            # Handle other exceptions (e.g., permission denied)
            sys.stderr.write(f"Error watching file {path}: {e}\n")
            continue

        if current_mtime != last_mtime:
            last_mtime = current_mtime
            with state._debounce_lock:
                if not state._debounced:
                    state._set_value(path)
                state._debounced = False


class FileState(PathState):
    """Wrapper for file state."""

    _forbidden_attributes = {
        "open",
        "iterdir",
        "glob",
        "rglob",
        "mkdir",
        "rename",
        "replace",
        "walk",
    }
    _target: Callable[[Path, FileState, threading.Event], None] = staticmethod(
        watch_file
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._debounced = False
        self._debounce_lock = threading.Lock()

    def read_text(self) -> str:
        """Read the file as a string."""
        text = self._value.read_text()
        write_side_effect(f"read_text:{text}")
        return text

    def write_text(self, value: str) -> int:
        """Write the file as a string."""
        response = self._value.write_text(value)
        text = self._value.read_text()
        write_side_effect(f"write_text:{text}")
        with self._debounce_lock:
            self._debounced = True
            self._set_value(self._value)
        return response

    def read_bytes(self) -> bytes:
        """Read the file as bytes."""
        data = self._value.read_bytes()
        write_side_effect(f"read_bytes:{data!r}")
        return data

    def write_bytes(self, value: bytes) -> int:
        """Write the file as bytes."""
        response = self._value.write_bytes(value)
        data = self._value.read_bytes()
        write_side_effect(f"write_bytes:{data!r}")
        with self._debounce_lock:
            self._debounced = True
            self._set_value(self._value)
        return response

    def __repr__(self) -> str:
        """Return a string representation of the file state."""
        if not self._value.exists():
            return f"FileState({self._value}: File not found)"
        _hash = hashlib.sha256(self._value.read_bytes()).hexdigest()
        return f"FileState({self._value}: {_hash})"


@mddoc
def file(path: Path | str) -> FileState:
    """
    A reactive wrapper for file paths.

    This function takes a file path to watch and returns a wrapper to reactively
    read and write from the file.

    The "wrapped" file Path object exposes most of the same methods as the
    [pathlib.Path object](https://docs.python.org/3/library/pathlib.html#pathlib.Path),
    with a few exceptions. The following methods are not available:

    - `open()`
    - `rename()`
    - `replace()`

    This object will trigger dependent cells to re-evaluate when the file is
    changed.

    Warning:
        It is possible to misuse this API in similar ways to `state()`. Consider
        reading the warning and caveats in the
        [`state()` documentation](state.md), and using this function only when
        reading file paths, and not when writing them.

    Args:
      path: Path to watch.

    Returns:
        A reactive wrapper for watching the file path.
    """
    if isinstance(path, str):
        path = Path(path)
    if path.is_dir():
        raise ValueError(
            "Path must be a file, not a directory, use mo.directory() instead"
        )
    return FileState(path, allow_self_loops=True)
