# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from marimo._output.rich_help import mddoc
from marimo._runtime.context import (
    ContextNotInitializedError,
    get_context,
    runtime_context_installed,
)
from marimo._runtime.side_effect import SideEffect
from marimo._runtime.state import State
from marimo._runtime.threads import Thread

T = TypeVar("T")


MODULE_WATCHER_SLEEP_INTERVAL = 1.0

# For testing only - do not use in production
_TEST_SLEEP_INTERVAL: float | None = None


def write_side_effect(data: str | bytes) -> None:
    """Write side effect to the context."""
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        # Context is not initialized, nothing we can do
        return
    ctx.cell_lifecycle_registry.add(SideEffect(data))


def watch_file(
    path: Path, state: FileState, should_exit: threading.Event
) -> None:
    """Watch a file for changes and update the state."""
    last_mtime = 0
    current_mtime = last_mtime
    sleep_interval = _TEST_SLEEP_INTERVAL or MODULE_WATCHER_SLEEP_INTERVAL
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
            state._set_value(path)


def watch_directory(
    path: Path, state: DirectoryState, should_exit: threading.Event
) -> None:
    """Watch a directory for changes and update the state."""
    print([k for k in path.walk()])
    last_structure = set((p, *map(tuple, r)) for p, *r in path.walk())
    current_structure = last_structure
    sleep_interval = _TEST_SLEEP_INTERVAL or MODULE_WATCHER_SLEEP_INTERVAL
    while not should_exit.is_set():
        time.sleep(sleep_interval)
        try:
            current_structure = set(
                (p, *map(tuple, r)) for p, *r in path.walk()
            )
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


class PathState(State[Path]):
    """Base class for path state."""

    _forbidden_attributes: set[str]
    _target: Callable[[Path, State, threading.Event], None]

    def __init__(
        self,
        path: Path,
        *args: Any,
        allow_self_loops: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            path,
            *args,
            allow_self_loops=allow_self_loops,
            _context="file",
            **kwargs,
        )
        self._should_exit = threading.Event()
        # Only bother with the watcher if the context is installed
        # State is not enabled in script mode
        if runtime_context_installed():
            Thread(
                target=self._target,
                args=(path, self, self._should_exit),
                daemon=True,
            ).start()

    def __getattr__(self, name: str) -> Any:
        """Get an attribute from the file path."""
        # Disable some attributes
        if name in self._forbidden_attributes:
            raise AttributeError(
                f"'{self.__class__.__name__}' does not "
                f"expose attribute '{name}'"
            )
        if hasattr(self._value, name):
            return getattr(self._value, name)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def __del__(self) -> None:
        self._should_exit.set()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._value})"

    def exists(self) -> bool:
        """Check if the path exists."""
        exists = self._value.exists()
        if not exists:
            write_side_effect(f"doesn't exists:{self._value}")
        else:
            _ = self.read_text()
        return exists


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
    _target: Callable[[Path, State, threading.Event], None] = staticmethod(
        watch_file
    )

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
        return response

    def read_bytes(self) -> bytes:
        """Read the file as bytes."""
        data = self._value.read_bytes()
        write_side_effect(f"read_bytes:{data}")
        return data

    def write_bytes(self, value: bytes) -> int:
        """Write the file as bytes."""
        response = self._value.write_bytes(value)
        data = self._value.read_bytes()
        write_side_effect(f"write_bytes:{data}")
        return response


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
    _target: Callable[[Path, State, threading.Event], None] = staticmethod(
        watch_directory
    )

    def walk(self) -> iter[Path]:
        """Walk the directory."""
        items = list(self._value.walk())
        write_side_effect(f"walk:{items}")
        return iter(items)

    def iterdir(self) -> iter[Path]:
        """Iterate over the directory."""
        items = list(self._value.iterdir())
        write_side_effect(f"iterdir:{items}")
        return iter(items)

    def glob(self, pattern: str) -> iter[Path]:
        """Glob the directory."""
        items = list(self._value.glob(pattern))
        write_side_effect(f"glob:{items}")
        return iter(items)

    def rglob(self, pattern: str) -> iter[Path]:
        """Recursive glob the directory."""
        items = list(self._value.rglob(pattern))
        write_side_effect(f"rglob:{items}")
        return iter(items)


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
        reading the warning and caveats in the `state()` documentation, and
        using this function only when reading file paths, and not when writing
        them.

    Args:
      path: Path to watch.

    Returns:
        A reactive wrapper for watching the file path.
    """
    if isinstance(path, str):
        path = Path(path)
    if path.is_dir():
        raise ValueError(
            "Path must be a file, not a directory, usemo.directory()"
        )
    return FileState(path, allow_self_loops=True)


@mddoc
def directory(path: Path | str):
    """
    A reactive wrapper for directory paths.

    This function takes a directory path to watch and returns a wrapper to
    reactively list the contents of the directory.

    This object will trigger dependent cells to re-evaluate when the directory
    structure is changed (i.e., files are added or removed).

    NOTE: This function does NOT react to file content changes, only to changes
    in the directory structure. Utilize `mo.file()` to watch for changes in
    specific files. Additional note: this will not followe symlinks.

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
