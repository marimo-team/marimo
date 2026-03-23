# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._code_mode._context import AsyncCodeModeContext
from marimo._notebook.document import (
    NotebookCell,
    NotebookDocument,
    _current_document,
)
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t


def cmd(cell_id: str, code: str) -> ExecuteCellCommand:
    return ExecuteCellCommand(cell_id=CellId_t(cell_id), code=code)


def _ctx(k: Kernel) -> AsyncCodeModeContext:
    """Build an AsyncCodeModeContext with a document snapshot from the kernel."""
    _current_document.set(
        NotebookDocument(
            [
                NotebookCell(
                    id=cid, code=cell.code, name="", config=cell.config
                )
                for cid, cell in k.graph.cells.items()
            ]
        )
    )
    return AsyncCodeModeContext(k)


class TestCellsViewIndex:
    """Test integer indexing (positive and negative)."""

    async def test_positive_index(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
                cmd(cell_id="c", code="z = 3"),
            ]
        )
        ctx = _ctx(k)

        assert ctx.cells[0].id == "a"
        assert ctx.cells[1].id == "b"
        assert ctx.cells[2].id == "c"

    async def test_negative_index(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
                cmd(cell_id="c", code="z = 3"),
            ]
        )
        ctx = _ctx(k)

        assert ctx.cells[-1].id == "c"
        assert ctx.cells[-2].id == "b"
        assert ctx.cells[-3].id == "a"

    async def test_index_out_of_range(self, k: Kernel) -> None:
        await k.run([cmd(cell_id="a", code="x = 1")])
        ctx = _ctx(k)

        with pytest.raises(IndexError):
            ctx.cells[5]

        with pytest.raises(IndexError):
            ctx.cells[-5]


class TestCellsViewCellId:
    """Test lookup by cell ID string."""

    async def test_lookup_by_cell_id(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="abc", code="x = 1"),
                cmd(cell_id="def", code="y = 2"),
            ]
        )
        ctx = _ctx(k)

        cell = ctx.cells["def"]
        assert cell.id == "def"
        assert cell.code == "y = 2"

    async def test_lookup_by_cell_id_not_found(self, k: Kernel) -> None:
        await k.run([cmd(cell_id="abc", code="x = 1")])
        ctx = _ctx(k)

        with pytest.raises(KeyError):
            ctx.cells["nonexistent"]


class TestCellsViewCellName:
    """Test lookup by cell name."""

    async def test_name_lookup_without_cell_manager(self, k: Kernel) -> None:
        await k.run([cmd(cell_id="a", code="x = 1")])
        ctx = _ctx(k)

        # No cell manager → name lookup fails
        with pytest.raises(KeyError):
            ctx.cells["my_cell"]


class TestCellsViewNameField:
    """Test that the name field is populated on NotebookCell."""

    async def test_name_is_empty_without_cell_manager(self, k: Kernel) -> None:
        await k.run([cmd(cell_id="a", code="x = 1")])
        ctx = _ctx(k)

        cell = ctx.cells[0]
        assert cell.name == ""


class TestCellsViewIteration:
    """Test iteration and len."""

    async def test_len(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        ctx = _ctx(k)
        assert len(ctx.cells) == 2

    async def test_iteration_yields_cell_ids(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        ctx = _ctx(k)

        ids = list(ctx.cells)
        assert ids == ["a", "b"]

    async def test_keys(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        ctx = _ctx(k)
        assert ctx.cells.keys() == ["a", "b"]

    async def test_values(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        ctx = _ctx(k)
        vals = ctx.cells.values()
        assert [v.id for v in vals] == ["a", "b"]
        assert [v.code for v in vals] == ["x = 1", "y = 2"]

    async def test_items(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        ctx = _ctx(k)
        items = ctx.cells.items()
        assert [(cid, cell.code) for cid, cell in items] == [
            ("a", "x = 1"),
            ("b", "y = 2"),
        ]

    async def test_contains(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        ctx = _ctx(k)
        assert "a" in ctx.cells
        assert "nonexistent" not in ctx.cells
        assert 0 in ctx.cells
        assert 5 not in ctx.cells
