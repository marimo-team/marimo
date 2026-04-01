# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable


class Disposable:
    """A callable wrapper around a cleanup action that can be invoked exactly once."""

    def __init__(self, action: Callable[[], None]) -> None:
        self.action = action
        self._is_disposed = False

    def __call__(self) -> None:
        return self.dispose()

    def dispose(self) -> None:
        """Execute the cleanup action and mark this disposable as disposed."""
        self.action()
        self._is_disposed = True

    def is_disposed(self) -> bool:
        """Return True if the cleanup action has already been executed."""
        return self._is_disposed

    @staticmethod
    def empty() -> Disposable:
        """Return a Disposable whose cleanup action is a no-op."""
        return Disposable(lambda: None)
