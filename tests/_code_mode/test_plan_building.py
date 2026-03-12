# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest
from inline_snapshot import snapshot

from marimo._ast.cell import CellConfig
from marimo._code_mode._context import _build_plan, _PlanEntry
from marimo._code_mode._edits import NotebookCellData, NotebookEdit
from marimo._types.ids import CellId_t


def ids(*names: str) -> list[CellId_t]:
    return [CellId_t(n) for n in names]


def cell(code: str, **kwargs: object) -> NotebookCellData:
    return NotebookCellData(code=code, cell_id=CellId_t(code), **kwargs)


def codes(plan: list[_PlanEntry]) -> list[str | None]:
    return [e.code for e in plan]


def cell_ids(plan: list[_PlanEntry]) -> list[str]:
    return [str(e.cell_id) for e in plan]


class TestInsert:
    def test_insert_at_start(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [NotebookEdit.insert_cells(0, [cell("new")])],
        )
        assert cell_ids(plan) == snapshot(["new", "a", "b", "c"])
        assert codes(plan) == snapshot(["new", None, None, None])

    def test_insert_at_end(self) -> None:
        plan = _build_plan(
            ids("a", "b"),
            [NotebookEdit.insert_cells(99, [cell("new")])],
        )
        assert cell_ids(plan) == snapshot(["a", "b", "new"])

    def test_insert_in_middle(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [NotebookEdit.insert_cells(1, [cell("new")])],
        )
        assert cell_ids(plan) == snapshot(["a", "new", "b", "c"])

    def test_insert_multiple(self) -> None:
        plan = _build_plan(
            ids("a", "b"),
            [NotebookEdit.insert_cells(1, [cell("x"), cell("y")])],
        )
        assert cell_ids(plan) == snapshot(["a", "x", "y", "b"])

    def test_insert_into_empty(self) -> None:
        plan = _build_plan([], [NotebookEdit.insert_cells(0, [cell("first")])])
        assert cell_ids(plan) == snapshot(["first"])
        assert codes(plan) == snapshot(["first"])

    def test_insert_without_code_raises(self) -> None:
        with pytest.raises(ValueError, match="code is required"):
            _build_plan(
                ids("a"),
                [NotebookEdit.insert_cells(0, [NotebookCellData()])],
            )


class TestDelete:
    def test_delete_single(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [NotebookEdit.delete_cells(1, 2)],
        )
        assert cell_ids(plan) == snapshot(["a", "c"])

    def test_delete_range(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [NotebookEdit.delete_cells(0, 2)],
        )
        assert cell_ids(plan) == snapshot(["c"])

    def test_delete_all(self) -> None:
        plan = _build_plan(
            ids("a", "b"),
            [NotebookEdit.delete_cells(0, 2)],
        )
        assert cell_ids(plan) == snapshot([])


class TestReplace:
    def test_replace_code(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [NotebookEdit.replace_cells(1, [NotebookCellData(code="new")])],
        )
        # cell_id preserved, code updated
        assert cell_ids(plan) == snapshot(["a", "b", "c"])
        assert codes(plan) == snapshot([None, "new", None])

    def test_replace_code_none_keeps_existing(self) -> None:
        plan = _build_plan(
            ids("a", "b"),
            [NotebookEdit.replace_cells(0, [NotebookCellData()])],
        )
        assert codes(plan) == snapshot([None, None])

    def test_replace_config_only(self) -> None:
        cfg = CellConfig(hide_code=True)
        plan = _build_plan(
            ids("a"),
            [NotebookEdit.replace_cells(0, [NotebookCellData(config=cfg)])],
        )
        assert plan[0].config == cfg
        assert plan[0].code is None

    def test_replace_preserves_config_when_not_provided(self) -> None:
        cfg = CellConfig(disabled=True)
        plan = _build_plan(
            ids("a"),
            [
                # First edit sets config
                NotebookEdit.replace_cells(0, [NotebookCellData(config=cfg)]),
                # Second edit changes code but not config
                NotebookEdit.replace_cells(
                    0, [NotebookCellData(code="updated")]
                ),
            ],
        )
        assert plan[0].config == cfg
        assert plan[0].code == "updated"

    def test_replace_out_of_bounds(self) -> None:
        with pytest.raises(IndexError, match="out of range"):
            _build_plan(
                ids("a"),
                [NotebookEdit.replace_cells(5, [NotebookCellData(code="x")])],
            )

    def test_replace_draft(self) -> None:
        plan = _build_plan(
            ids("a"),
            [
                NotebookEdit.replace_cells(
                    0, [NotebookCellData(code="x", draft=True)]
                )
            ],
        )
        assert plan[0].draft is True


class TestCombined:
    def test_delete_then_insert(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [
                NotebookEdit.delete_cells(1, 2),
                NotebookEdit.insert_cells(1, [cell("new")]),
            ],
        )
        assert cell_ids(plan) == snapshot(["a", "new", "c"])

    def test_insert_then_replace(self) -> None:
        plan = _build_plan(
            ids("a", "b"),
            [
                NotebookEdit.insert_cells(1, [cell("tmp")]),
                NotebookEdit.replace_cells(
                    1, [NotebookCellData(code="final")]
                ),
            ],
        )
        assert cell_ids(plan) == snapshot(["a", "tmp", "b"])
        assert codes(plan) == snapshot([None, "final", None])

    def test_multiple_inserts(self) -> None:
        plan = _build_plan(
            ids("a"),
            [
                NotebookEdit.insert_cells(0, [cell("first")]),
                NotebookEdit.insert_cells(2, [cell("last")]),
            ],
        )
        assert cell_ids(plan) == snapshot(["first", "a", "last"])
