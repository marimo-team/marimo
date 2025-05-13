# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast

from marimo._output.rich_help import mddoc
from marimo._runtime.watch._path import (
    WATCHER_SLEEP_INTERVAL,
    PathState,
    write_side_effect,
)

if TYPE_CHECKING:
    import threading
    from collections.abc import Iterable


# For testing only - do not use in production
_TEST_SLEEP_INTERVAL: float | None = None


def walk(path: Path) -> Iterable[tuple[Path, list[str], list[str]]]:
    if sys.version_info >= (3, 12):
        return path.walk()
    return os.walk(path)


def _hashable_walk(
    walked: Iterable[tuple[Path, list[str], list[str]]],
) -> set[tuple[Path, tuple[str], tuple[str]]]:
    return cast(
        set[tuple[Path, tuple[str], tuple[str]]],
        set((p, *map(tuple, r)) for p, *r in walked),
    )


def hashable_walk(path: Path) -> set[tuple[Path, tuple[str], tuple[str]]]:
    return _hashable_walk(walk(path))


def watch_directory(
    path: Path, state: DirectoryState, should_exit: threading.Event
) -> None:
    """Watch a directory for changes and update the state."""
    last_structure = hashable_walk(path)
    current_structure = last_structure
    sleep_interval = _TEST_SLEEP_INTERVAL or WATCHER_SLEEP_INTERVAL
    while not should_exit.is_set():
        time.sleep(sleep_interval)
        try:
            current_structure = hashable_walk(path)
        except FileNotFoundError:
            # Directory has been deleted, trigger a change
            current_structure = set()
        except Exception as e:
            # Handle other exceptions (e.g., permission denied)
            sys.stderr.write(f"Error watching directory {path}: {e}\n")
            continue

        if current_structure != last_structure:
            last_structure = current_structure
            state._set_value(path)


class DirectoryState(PathState):
    """Wrapper for directory state."""

    _forbidden_attributes = {
        "open",
        "rename",
        "replace",
        "remove",
        "unlink",
        "write_text",
        "write_bytes",
        "read_text",
        "read_bytes",
        "mkdir",
        "touch",
    }
    _target: Callable[[Path, DirectoryState, threading.Event], None] = (
        staticmethod(watch_directory)
    )

    def walk(self) -> Iterable[tuple[Path, list[str], list[str]]]:
        """Walk the directory."""
        items = walk(self._value)
        as_list = list(_hashable_walk(items))
        write_side_effect(f"walk:{sorted(as_list)}")
        return iter(items)

    def iterdir(self) -> Iterable[Path]:
        """Iterate over the directory."""
        items = list(self._value.iterdir())
        write_side_effect(f"iterdir:{items}")
        return iter(items)

    def glob(self, pattern: str) -> Iterable[Path]:
        """Glob the directory."""
        items = list(self._value.glob(pattern))
        write_side_effect(f"glob:{items}")
        return iter(items)

    def rglob(self, pattern: str) -> Iterable[Path]:
        """Recursive glob the directory."""
        items = list(self._value.rglob(pattern))
        write_side_effect(f"rglob:{items}")
        return iter(items)

    def __repr__(self) -> str:
        """Return a string representation of the file state."""
        _walk = self.walk()  # Call to issue side effect
        _hash = hashlib.sha256(f"{list(_walk)}".encode()).hexdigest()
        return f"DirectoryState({self._value}: {_hash})"


@mddoc
def directory(path: Path | str) -> DirectoryState:
    """
    A reactive wrapper for directory paths.

    This function takes a directory path to watch and returns a wrapper to
    reactively list the contents of the directory.

    This object will trigger dependent cells to re-evaluate when the directory
    structure is changed (i.e., files are added or removed).

    NOTE: This function does NOT react to file content changes, only to changes
    in the directory structure. Utilize `mo.file()` to watch for changes in
    specific files. Additional note: this will not follow symlinks.

    Args:
      path: Path to watch.

    Returns:
        A reactive wrapper for watching the directory.
    """

    if isinstance(path, str):
        path = Path(path)
    if not path.is_dir():
        raise ValueError("Path must be a directory, use mo.file()")
    return DirectoryState(path, allow_self_loops=True)
