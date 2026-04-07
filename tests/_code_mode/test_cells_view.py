# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

import re

from inline_snapshot import snapshot

from marimo._ast.cell import CellConfig
from marimo._code_mode._context import (
    AsyncCodeModeContext,
    NotebookCell as EnrichedCell,
    _CellsView,
)
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
    return _CellsView(ctx)


# ------------------------------------------------------------------
# __repr__
# ------------------------------------------------------------------


class TestCellsViewRepr:
    def test_repr_empty(self) -> None:
        v = _view([])
        assert repr(v) == snapshot("CellsView(0 cells):")

    def test_repr_single_cell(self) -> None:
        v = _view([_cell("a1", "x = 1")])
        assert repr(v) == snapshot("""\
CellsView(1 cell):
  [0] a1 [stale] | x = 1""")

    def test_repr_multiple_cells(self) -> None:
        v = _view([_cell("a", "x = 1"), _cell("b", "y = 2")])
        assert repr(v) == snapshot("""\
CellsView(2 cells):
  [0] a [stale] | x = 1
  [1] b [stale] | y = 2""")

    def test_repr_with_name(self) -> None:
        v = _view([_cell("a", "import marimo as mo", name="setup")])
        assert "(setup)" in repr(v)

    def test_repr_long_code_truncated(self) -> None:
        long_code = "x = " + "a" * 60
        v = _view([_cell("a", long_code)])
        r = repr(v)
        assert "..." in r
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
        assert "[9]" in r
        assert "[14]" in r
        assert "... 4 more cells ..." in r
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


# ------------------------------------------------------------------
# NotebookCell (enriched) status
# ------------------------------------------------------------------


@dataclasses.dataclass
class _MockImpl:
    """Minimal stand-in for CellImpl — satisfies ``CellRuntimeState`` protocol."""

    code: str = ""
    runtime_state: str | None = None
    run_result_status: str | None = None
    stale: bool = False
    exception: Exception | None = None


class TestEnrichedCellStatus:
    def test_no_impl_empty_returns_none(self) -> None:
        cell = _cell("a", "")
        enriched = EnrichedCell(cell, None)
        assert enriched.status is None

    def test_no_impl_with_code_returns_stale(self) -> None:
        cell = _cell("a", "x = 1")
        enriched = EnrichedCell(cell, None)
        assert enriched.status == "stale"

    def test_success_maps_to_idle(self) -> None:
        cell = _cell("a", "x = 1")
        impl = _MockImpl(code="x = 1", run_result_status="success")
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "idle"

    def test_exception_status(self) -> None:
        err = ValueError("boom")
        cell = _cell("a", "x = 1")
        impl = _MockImpl(
            code="x = 1", run_result_status="exception", exception=err
        )
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "exception"
        assert len(enriched.errors) == 1
        assert enriched.errors[0].kind == "runtime"
        assert enriched.errors[0].exception is err

    def test_code_edited_becomes_stale(self) -> None:
        cell = _cell("a", "x = 2")
        impl = _MockImpl(code="x = 1", run_result_status="success")
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "stale"

    def test_code_edited_after_error_becomes_stale(self) -> None:
        err = ZeroDivisionError()
        cell = _cell("a", "x = 1")
        impl = _MockImpl(
            code="1 / 0", run_result_status="exception", exception=err
        )
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "stale"
        # Error persists for inspection
        assert len(enriched.errors) == 1
        assert enriched.errors[0].exception is err

    def test_runtime_stale_flag(self) -> None:
        """Lazy mode: inputs changed but code is the same."""
        cell = _cell("a", "y = x + 1")
        impl = _MockImpl(
            code="y = x + 1", run_result_status="success", stale=True
        )
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "stale"

    def test_registered_but_never_run_is_stale(self) -> None:
        """Cell registered in graph with matching code but never executed."""
        cell = _cell("a", "x = 1")
        impl = _MockImpl(code="x = 1")  # run_result_status=None
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "stale"

    def test_registered_empty_never_run_is_none(self) -> None:
        """Empty cell registered in graph but never executed."""
        cell = _cell("a", "")
        impl = _MockImpl(code="")
        enriched = EnrichedCell(cell, impl)
        assert enriched.status is None

    def test_queued_takes_priority(self) -> None:
        cell = _cell("a", "x = 1")
        impl = _MockImpl(code="x = 1", runtime_state="queued")
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "queued"

    def test_running_takes_priority(self) -> None:
        cell = _cell("a", "x = 1")
        impl = _MockImpl(code="x = 1", runtime_state="running")
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "running"

    def test_disabled_transitively_maps_to_disabled(self) -> None:
        cell = _cell("a", "x = 1")
        impl = _MockImpl(code="x = 1", runtime_state="disabled-transitively")
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "disabled"

    def test_cancelled_status(self) -> None:
        cell = _cell("a", "x = 1")
        impl = _MockImpl(code="x = 1", run_result_status="cancelled")
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "cancelled"

    def test_marimo_error_status(self) -> None:
        cell = _cell("a", "x = 1")
        impl = _MockImpl(code="x = 1", run_result_status="marimo-error")
        enriched = EnrichedCell(cell, impl)
        assert enriched.status == "marimo-error"

    def test_delegates_document_properties(self) -> None:
        cell = _cell("a1", "x = 1", name="my_cell")
        enriched = EnrichedCell(cell, None)
        assert enriched.id == "a1"
        assert enriched.code == "x = 1"
        assert enriched.name == "my_cell"
        assert enriched.config == CellConfig()

    def test_errors_empty_when_no_impl(self) -> None:
        cell = _cell("a", "x = 1")
        enriched = EnrichedCell(cell, None)
        assert enriched.errors == []


class TestEnrichedCellRepr:
    def test_repr_no_impl_with_code(self) -> None:
        cell = _cell("a1", "x = 1")
        enriched = EnrichedCell(cell, None)
        assert repr(enriched) == snapshot(
            "NotebookCell(id='a1', status='stale', code='x = 1')"
        )

    def test_repr_no_impl_empty(self) -> None:
        cell = _cell("a1", "")
        enriched = EnrichedCell(cell, None)
        assert repr(enriched) == snapshot("NotebookCell(id='a1', code='')")

    def test_repr_with_status(self) -> None:
        cell = _cell("a1", "x = 1")
        impl = _MockImpl(code="x = 1", run_result_status="exception")
        enriched = EnrichedCell(cell, impl)
        assert repr(enriched) == snapshot(
            "NotebookCell(id='a1', status='exception', code='x = 1')"
        )

    def test_repr_with_name_and_status(self) -> None:
        cell = _cell("a1", "import os", name="setup")
        impl = _MockImpl(code="import os", run_result_status="success")
        enriched = EnrichedCell(cell, impl)
        assert repr(enriched) == snapshot(
            "NotebookCell(id='a1', name='setup', status='idle', code='import os')"
        )

    def test_repr_stale_from_code_edit(self) -> None:
        cell = _cell("a1", "x = 2")
        impl = _MockImpl(code="x = 1", run_result_status="success")
        enriched = EnrichedCell(cell, impl)
        assert repr(enriched) == snapshot(
            "NotebookCell(id='a1', status='stale', code='x = 2')"
        )


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
