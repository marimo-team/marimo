# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from marimo._plugins.ui._core.ui_element import UIElement

__all__ = ["UIElementStub"]

S = TypeVar("S")
T = TypeVar("T")


class UIElementStub(Generic[S, T]):
    """Stub for UIElement objects, storing args and hashable data."""

    def __init__(self, element: UIElement[S, T]) -> None:
        self.args = element._args
        self.cls = element.__class__
        # Ideally only hashable attributes are stored on the subclass level.
        defaults = set(self.cls.__new__(self.cls).__dict__.keys())
        defaults |= {"_ctx"}
        self.data = {
            k: v
            for k, v in element.__dict__.items()
            if hasattr(v, "__hash__") and k not in defaults
        }

    def load(self) -> UIElement[S, T]:
        """Reconstruct the UIElement from stored data."""
        return self.cls.from_args(self.data, self.args)  # type: ignore
