# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

import re

from marimo._ast.cell import CellConfig
from marimo._code_mode._context import AsyncCodeModeContext, _CellsView
from marimo._messaging.notebook.document import (
    NotebookCell,
    NotebookDocument,
    notebook_document_context,
)
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t


def cmd(cell_id: str, code: str) -> ExecuteCellCommand:
    return ExecuteCellCommand(cell_id=CellId_t(cell_id), code=code)


@contextmanager
def _ctx(k: Kernel) -> Generator[AsyncCodeModeContext, None, None]:
    """Build an AsyncCodeModeContext with a document snapshot from the kernel."""
    doc = NotebookDocument(
        [
            NotebookCell(id=cid, code=cell.code, name="", config=cell.config)
            for cid, cell in k.graph.cells.items()
        ]
    )
    with notebook_document_context(doc):
        yield AsyncCodeModeContext(k)


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
        with _ctx(k) as ctx:
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
        with _ctx(k) as ctx:
            assert ctx.cells[-1].id == "c"
            assert ctx.cells[-2].id == "b"
            assert ctx.cells[-3].id == "a"

    async def test_index_out_of_range(self, k: Kernel) -> None:
        await k.run([cmd(cell_id="a", code="x = 1")])
        with _ctx(k) as ctx:
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
        with _ctx(k) as ctx:
            cell = ctx.cells["def"]
            assert cell.id == "def"
            assert cell.code == "y = 2"

    async def test_lookup_by_cell_id_not_found(self, k: Kernel) -> None:
        await k.run([cmd(cell_id="abc", code="x = 1")])
        with _ctx(k) as ctx:
            with pytest.raises(KeyError):
                ctx.cells["nonexistent"]


class TestCellsViewCellName:
    """Test lookup by cell name."""

    async def test_name_lookup_without_cell_manager(self, k: Kernel) -> None:
        await k.run([cmd(cell_id="a", code="x = 1")])
        with _ctx(k) as ctx:
            # No cell manager → name lookup fails
            with pytest.raises(KeyError):
                ctx.cells["my_cell"]


class TestCellsViewNameField:
    """Test that the name field is populated on NotebookCell."""

    async def test_name_is_empty_without_cell_manager(self, k: Kernel) -> None:
        await k.run([cmd(cell_id="a", code="x = 1")])
        with _ctx(k) as ctx:
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
        with _ctx(k) as ctx:
            assert len(ctx.cells) == 2

    async def test_iteration_yields_cells(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        with _ctx(k) as ctx:
            cells = list(ctx.cells)
            assert [c.id for c in cells] == ["a", "b"]
            assert [c.code for c in cells] == ["x = 1", "y = 2"]

    async def test_keys(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        with _ctx(k) as ctx:
            assert ctx.cells.keys() == ["a", "b"]

    async def test_values(self, k: Kernel) -> None:
        await k.run(
            [
                cmd(cell_id="a", code="x = 1"),
                cmd(cell_id="b", code="y = 2"),
            ]
        )
        with _ctx(k) as ctx:
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
        with _ctx(k) as ctx:
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
        with _ctx(k) as ctx:
            assert "a" in ctx.cells
            assert "nonexistent" not in ctx.cells
            assert 0 in ctx.cells
            assert 5 not in ctx.cells


# ------------------------------------------------------------------
# Lightweight helper (no kernel needed)
# ------------------------------------------------------------------


def _cell(cell_id: str, code: str, name: str = "") -> NotebookCell:
    return NotebookCell(
        id=CellId_t(cell_id), code=code, name=name, config=CellConfig()
    )


def _view(cells: list[NotebookCell]) -> _CellsView:
    doc = NotebookDocument(cells)
    ctx = type("_MockCtx", (), {"_document": doc})()
    return _CellsView(ctx)  # type: ignore[arg-type]


# ------------------------------------------------------------------
# __repr__
# ------------------------------------------------------------------


class TestCellsViewRepr:
    def test_repr_empty(self) -> None:
        v = _view([])
        assert repr(v) == "CellsView(0 cells):"

    def test_repr_single_cell(self) -> None:
        v = _view([_cell("a1", "x = 1")])
        r = repr(v)
        assert r.startswith("CellsView(1 cell):")
        assert "[0] a1 | x = 1" in r

    def test_repr_multiple_cells(self) -> None:
        v = _view([_cell("a", "x = 1"), _cell("b", "y = 2")])
        r = repr(v)
        assert "CellsView(2 cells):" in r
        assert "[0] a | x = 1" in r
        assert "[1] b | y = 2" in r

    def test_repr_with_name(self) -> None:
        v = _view([_cell("a", "import marimo as mo", name="setup")])
        assert "(setup)" in repr(v)

    def test_repr_long_code_truncated(self) -> None:
        long_code = "x = " + "a" * 60
        v = _view([_cell("a", long_code)])
        r = repr(v)
        assert "..." in r
        # First 50 chars of first line + "..."
        assert long_code[:50] + "..." in r

    def test_repr_multiline_shows_first_line(self) -> None:
        v = _view([_cell("a", "line1\nline2\nline3")])
        r = repr(v)
        assert "line1" in r
        assert "line2" not in r

    def test_str_equals_repr(self) -> None:
        v = _view([_cell("a", "x = 1")])
        assert str(v) == repr(v)

    def test_repr_many_cells_truncated(self) -> None:
        cells = [_cell(f"c{i}", f"x{i} = {i}") for i in range(15)]
        v = _view(cells)
        r = repr(v)
        assert "CellsView(15 cells):" in r
        # First 10 shown
        assert "[9]" in r
        # Last cell shown
        assert "[14]" in r
        # Middle omitted
        assert "... 4 more cells ..." in r
        # Cell 11 not individually shown
        assert "[11]" not in r


# ------------------------------------------------------------------
# NotebookCell.__repr__
# ------------------------------------------------------------------


class TestNotebookCellRepr:
    def test_repr_basic(self) -> None:
        c = _cell("a1", "x = 1")
        assert repr(c) == "NotebookCell(id='a1', code='x = 1')"

    def test_repr_with_name(self) -> None:
        c = _cell("a1", "import marimo as mo", name="setup")
        assert repr(c) == (
            "NotebookCell(id='a1', name='setup', code='import marimo as mo')"
        )

    def test_repr_long_code_truncated(self) -> None:
        long_code = "x = " + "a" * 100
        c = _cell("a1", long_code)
        r = repr(c)
        assert "..." in r
        assert long_code[:80] in r

    def test_repr_multiline_shows_first_line(self) -> None:
        c = _cell("a1", "line1\nline2\nline3")
        r = repr(c)
        assert "line1..." in r
        assert "line2" not in r

    def test_repr_empty_code(self) -> None:
        c = _cell("a1", "")
        assert repr(c) == "NotebookCell(id='a1', code='')"


# ------------------------------------------------------------------
# find()
# ------------------------------------------------------------------


class TestCellsViewFind:
    def test_find_match(self) -> None:
        v = _view([_cell("a", "import marimo"), _cell("b", "x = 1")])
        result = v.find("import")
        assert len(result) == 1
        assert result[0].id == "a"

    def test_find_no_match(self) -> None:
        v = _view([_cell("a", "x = 1")])
        assert v.find("pandas") == []

    def test_find_multiple_matches(self) -> None:
        v = _view(
            [
                _cell("a", "import os"),
                _cell("b", "x = 1"),
                _cell("c", "import sys"),
            ]
        )
        result = v.find("import")
        assert [c.id for c in result] == ["a", "c"]

    def test_find_case_sensitive(self) -> None:
        v = _view([_cell("a", "import os")])
        assert v.find("Import") == []


# ------------------------------------------------------------------
# grep()
# ------------------------------------------------------------------


class TestCellsViewGrep:
    def test_grep_literal(self) -> None:
        v = _view([_cell("a", "x = 1"), _cell("b", "y = 2")])
        result = v.grep("x = 1")
        assert len(result) == 1
        assert result[0].id == "a"

    def test_grep_regex(self) -> None:
        v = _view(
            [
                _cell("a", "x = 1"),
                _cell("b", "x=42"),
                _cell("c", "y = 2"),
            ]
        )
        result = v.grep(r"x\s*=\s*\d+")
        assert [c.id for c in result] == ["a", "b"]

    def test_grep_no_match(self) -> None:
        v = _view([_cell("a", "x = 1")])
        assert v.grep(r"zzz\d+") == []

    def test_grep_multiline_cell(self) -> None:
        v = _view([_cell("a", "line1\nline2_match\nline3")])
        result = v.grep("line2_match")
        assert len(result) == 1

    def test_grep_invalid_regex_raises(self) -> None:
        v = _view([_cell("a", "x = 1")])
        with pytest.raises(re.error):
            v.grep("[invalid")


# ------------------------------------------------------------------
# Error messages
# ------------------------------------------------------------------


class TestCellsViewErrorMessages:
    def test_error_lists_available_ids(self) -> None:
        v = _view([_cell("abcd", "x = 1"), _cell("efgh", "y = 2")])
        with pytest.raises(KeyError, match="not found"):
            v["MzAK"]

    def test_error_mentions_stability(self) -> None:
        v = _view([_cell("abcd", "x = 1")])
        with pytest.raises(KeyError, match="stable across reorders"):
            v["gone"]

    def test_error_shows_available(self) -> None:
        v = _view([_cell("abcd", "x = 1")])
        with pytest.raises(KeyError, match="abcd"):
            v["missing"]
