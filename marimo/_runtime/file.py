# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TypeVar, Any
from pathlib import Path

from marimo._output.rich_help import mddoc
from marimo._runtime.state import State

from marimo._runtime.context import ContextNotInitializedError, get_context

T = TypeVar("T")

class FileState(State[Path]):
    """Wrapper for file state."""
    def __init__(self, path: Path, *args: Any, allow_self_loops: bool =
                 True, **kwargs: Any) -> None:
        super().__init__(path, *args, allow_self_loops=allow_self_loops,
                         _context="file", **kwargs)

    def read_text(self) -> str:
        """Read the file as a string."""
        return self._value.read_text()

    def write_text(self, value:str) -> int:
        """Write the file as a string."""
        return self._value.write_text(value)

    def read_bytes(self) -> bytes:
        """Read the file as bytes."""
        return self._value.read_bytes()

    def write_bytes(self, value:bytes) -> int:
        """Write the file as bytes."""
        return self._value.write_bytes(value)

    def __repr__(self) -> str:
        return f"FileState({self._value})"


@mddoc
def file(
    path: Path
) -> FileState:
    """
    A reactive wrapper for file paths.

    Args:
      path: Path to watch.

    Returns:
        A reactive wrapper for the file path watching.
    """
    return FileState(path, allow_self_loops=True)

