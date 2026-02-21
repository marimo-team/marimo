# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._output.hypertext import Html


class CellOutputList:
    """Thread-safe container for a cell's accumulated output.

    Wraps a ``list[Html]`` with an ``RLock`` so that concurrent
    ``mo.Thread`` workers can safely mutate the shared output list.

    The lock is reentrant because ``clear`` delegates to ``replace``
    and ``remove`` delegates to ``flush``.
    """

    __slots__ = ("_items", "_lock")

    def __init__(self) -> None:
        self._items: list[Html] = []
        self._lock = threading.RLock()

    # -- public mutation helpers -------------------------------------------

    def append(self, item: Html) -> None:
        self._items.append(item)

    def clear(self) -> None:
        self._items.clear()

    def replace_at_index(self, item: Html, idx: int) -> None:
        if idx > len(self._items):
            raise IndexError(
                f"idx is {idx}, must be <= {len(self._items)}"
            )
        if idx == len(self._items):
            self._items.append(item)
        else:
            self._items[idx] = item

    def remove(self, value: object) -> None:
        self._items[:] = [
            item for item in self._items if item is not value
        ]

    # -- read helpers ------------------------------------------------------

    def stack(self) -> Html | None:
        """Return ``vstack`` of the items, or ``None`` if empty."""
        if self._items:
            from marimo._plugins.stateless.flex import vstack

            return vstack(self._items)
        return None

    # -- lock access -------------------------------------------------------

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    # -- dunder helpers ----------------------------------------------------

    def __bool__(self) -> bool:
        return bool(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"CellOutputList({self._items!r})"
