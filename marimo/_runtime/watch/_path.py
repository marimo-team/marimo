# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Callable, TypeVar

from marimo._runtime.context import (
    ContextNotInitializedError,
    get_context,
    runtime_context_installed,
)
from marimo._runtime.side_effect import SideEffect
from marimo._runtime.state import State
from marimo._runtime.threads import Thread

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


T = TypeVar("T")

WATCHER_SLEEP_INTERVAL = 1.0


def write_side_effect(data: str | bytes) -> None:
    """Write side effect to the context."""
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        # Context is not initialized, nothing we can do
        return
    ctx.cell_lifecycle_registry.add(SideEffect(data))


class PathState(State[Path]):
    """Base class for path state."""

    _forbidden_attributes: set[str]
    _target: Callable[[Path, Self, threading.Event], None]

    def __init__(
        self,
        path: Path,
        *args: Any,
        allow_self_loops: bool = True,
        **kwargs: Any,
    ) -> None:
        if kwargs.pop("_context", None) is not None:
            raise ValueError(
                "The '_context' argument is not supported for this class."
            )
        if kwargs.pop("allow_self_loops", None) is not None:
            raise ValueError(
                "The 'allow_self_loops' argument is not supported for this class."
            )

        # Mypy seems to think we could provide multiple kwargs definitions here
        # but we can't.
        super().__init__(
            path,
            *args,
            allow_self_loops=allow_self_loops,
            _context="file",
            **kwargs,
        )  # type: ignore[misc]
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
