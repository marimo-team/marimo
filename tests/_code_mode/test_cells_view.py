# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._code_mode._context import AsyncCodeModeContext, NotebookCellData
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runtime import Kernel


class TestCellsViewIndex:
    """Test integer indexing (positive and negative)."""

    async def test_positive_index(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="a", code="x = 1"),
                ExecuteCellCommand(cell_id="b", code="y = 2"),
                ExecuteCellCommand(cell_id="c", code="z = 3"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

        assert ctx.cells[0].cell_id == "a"
        assert ctx.cells[1].cell_id == "b"
        assert ctx.cells[2].cell_id == "c"

    async def test_negative_index(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="a", code="x = 1"),
                ExecuteCellCommand(cell_id="b", code="y = 2"),
                ExecuteCellCommand(cell_id="c", code="z = 3"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

        assert ctx.cells[-1].cell_id == "c"
        assert ctx.cells[-2].cell_id == "b"
        assert ctx.cells[-3].cell_id == "a"

    async def test_index_out_of_range(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="a", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        with pytest.raises(IndexError):
            ctx.cells[5]

        with pytest.raises(IndexError):
            ctx.cells[-5]


class TestCellsViewCellId:
    """Test lookup by cell ID string."""

    async def test_lookup_by_cell_id(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="abc", code="x = 1"),
                ExecuteCellCommand(cell_id="def", code="y = 2"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

        cell = ctx.cells["def"]
        assert cell.cell_id == "def"
        assert cell.code == "y = 2"

    async def test_lookup_by_cell_id_not_found(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="abc", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        with pytest.raises(KeyError):
            ctx.cells["nonexistent"]


class TestCellsViewCellName:
    """Test lookup by cell name."""

    async def test_name_lookup_without_cell_manager(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="a", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        # No cell manager → name lookup fails
        with pytest.raises(KeyError):
            ctx.cells["my_cell"]


class TestCellsViewNameField:
    """Test that the name field is populated on NotebookCellData."""

    async def test_name_is_none_without_cell_manager(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="a", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        cell = ctx.cells[0]
        assert cell.name is None

    async def test_name_field_on_constructed_cell(self) -> None:
        cell = NotebookCellData(code="x = 1", name="my_cell")
        assert cell.name == "my_cell"


class TestCellsViewIteration:
    """Test iteration and len."""

    async def test_len(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="a", code="x = 1"),
                ExecuteCellCommand(cell_id="b", code="y = 2"),
            ]
        )
        ctx = AsyncCodeModeContext(k)
        assert len(ctx.cells) == 2

    async def test_iteration(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="a", code="x = 1"),
                ExecuteCellCommand(cell_id="b", code="y = 2"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

        ids = [cell.cell_id for cell in ctx.cells]
        assert ids == ["a", "b"]
