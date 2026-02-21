# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._output.hypertext import Html


class CellOutputList:
    """Thread-safe container for a cell's imperatively constructed output."""

    def __init__(self) -> None:
        self._items: list[Html] = []
        self._lock = threading.RLock()

    def append(self, item: Html) -> None:
        with self._lock:
            self._items.append(item)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def replace_at_index(self, item: Html, idx: int) -> None:
        with self._lock:
            if idx > len(self._items):
                raise IndexError(
                    f"idx is {idx}, must be <= {len(self._items)}"
                )
            if idx == len(self._items):
                self._items.append(item)
            else:
                self._items[idx] = item

    def remove(self, value: object) -> None:
        with self._lock:
            self._items[:] = [
                item for item in self._items if item is not value
            ]

    def stack(self) -> Html | None:
        """Return `vstack` of the items, or `None` if empty."""
        with self._lock:
            if self._items:
                from marimo._plugins.stateless.flex import vstack

                return vstack(self._items)
        return None

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self._items)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def __repr__(self) -> str:
        with self._lock:
            return f"CellOutputList({self._items!r})"
