# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._code_mode._context import AsyncCodeModeContext
from marimo._code_mode._edits import NotebookCellData, NotebookEdit
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

    async def test_negative_index_has_correct_stored_index(
        self, k: Kernel
    ) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="a", code="x = 1"),
                ExecuteCellCommand(cell_id="b", code="y = 2"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

        cell = ctx.cells[-1]
        assert cell.cell_id == "b"
        # _index should be the normalized positive index
        assert cell._index == 1

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
        assert cell._index == 1

    async def test_lookup_by_cell_id_not_found(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="abc", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        with pytest.raises(KeyError):
            ctx.cells["nonexistent"]


class TestCellsViewCellName:
    """Test lookup by cell name.

    Cell name lookup requires a cell_manager, which is only available
    when the context is constructed with one (e.g., via get_context()).
    Without a cell manager, name lookups raise KeyError.
    """

    async def test_name_lookup_without_cell_manager(self, k: Kernel) -> None:
        await k.run([ExecuteCellCommand(cell_id="a", code="x = 1")])
        ctx = AsyncCodeModeContext(k)

        # No cell manager → name lookup fails
        with pytest.raises(KeyError):
            ctx.cells["my_cell"]


class TestCellsViewNameField:
    """Test that the name field is populated on NotebookCellData."""

    async def test_name_is_none_without_cell_manager(
        self, k: Kernel
    ) -> None:
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

    async def test_iteration_indices(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="a", code="x = 1"),
                ExecuteCellCommand(cell_id="b", code="y = 2"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

        indices = [cell._index for cell in ctx.cells]
        assert indices == [0, 1]


class TestCellsViewEdit:
    """Test that cells returned by the view can produce edits."""

    async def test_edit_from_negative_index(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="a", code="x = 1"),
                ExecuteCellCommand(cell_id="b", code="y = 2"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

        cell = ctx.cells[-1]
        edit = cell.edit(code="y = 99")
        # The edit should target the normalized index (1, not -1)
        assert edit.index == 1

    async def test_edit_from_cell_id_lookup(self, k: Kernel) -> None:
        await k.run(
            [
                ExecuteCellCommand(cell_id="a", code="x = 1"),
                ExecuteCellCommand(cell_id="b", code="y = 2"),
            ]
        )
        ctx = AsyncCodeModeContext(k)

        cell = ctx.cells["b"]
        edit = cell.edit(code="y = 99")
        assert edit.index == 1
