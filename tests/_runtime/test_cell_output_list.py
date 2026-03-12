# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from marimo._runtime.cell_output_list import CellOutputList


def _html(text: str) -> MagicMock:
    m = MagicMock()
    m.__repr__ = lambda _: text
    return m


class TestCellOutputList:
    def test_append_and_len(self) -> None:
        col = CellOutputList()
        assert len(col) == 0
        col.append(_html("a"))
        col.append(_html("b"))
        assert len(col) == 2

    def test_bool(self) -> None:
        col = CellOutputList()
        assert not col
        col.append(_html("a"))
        assert col

    def test_clear(self) -> None:
        col = CellOutputList()
        col.append(_html("a"))
        col.clear()
        assert len(col) == 0

    def test_replace_at_index(self) -> None:
        col = CellOutputList()
        col.append(_html("a"))
        col.append(_html("b"))
        replacement = _html("c")
        col.replace_at_index(replacement, 0)
        assert col._items[0] is replacement
        assert len(col) == 2

    def test_replace_at_index_appends_at_end(self) -> None:
        col = CellOutputList()
        col.append(_html("a"))
        new = _html("b")
        col.replace_at_index(new, 1)
        assert len(col) == 2
        assert col._items[1] is new

    def test_replace_at_index_out_of_range(self) -> None:
        col = CellOutputList()
        with pytest.raises(IndexError):
            col.replace_at_index(_html("a"), 5)

    def test_remove_by_identity(self) -> None:
        col = CellOutputList()
        a = _html("a")
        b = _html("b")
        col.append(a)
        col.append(b)
        col.remove(a)
        assert len(col) == 1
        assert col._items[0] is b

    def test_stack_empty_returns_none(self) -> None:
        col = CellOutputList()
        assert col.stack() is None
