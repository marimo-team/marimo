# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest
from inline_snapshot import snapshot

from marimo._ast.cell import CellConfig
from marimo._code_mode._plan import (
    _AddOp,
    _build_plan,
    _DeleteOp,
    _MoveOp,
    _PlanEntry,
    _UpdateOp,
    _validate_ops,
)
from marimo._types.ids import CellId_t


def ids(*names: str) -> list[CellId_t]:
    return [CellId_t(n) for n in names]


def cell_ids(plan: list[_PlanEntry]) -> list[str]:
    return [str(e.cell_id) for e in plan]


def codes(plan: list[_PlanEntry]) -> list[str | None]:
    return [e.code for e in plan]


class TestAdd:
    def test_append_at_end(self) -> None:
        plan = _build_plan(
            ids("a", "b"),
            [_AddOp(cell_id=CellId_t("new"), code="x", config=CellConfig())],
        )
        assert cell_ids(plan) == snapshot(["a", "b", "new"])
        assert codes(plan) == snapshot([None, None, "x"])

    def test_add_after(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [
                _AddOp(
                    cell_id=CellId_t("new"),
                    code="x",
                    config=CellConfig(),
                    after=CellId_t("a"),
                )
            ],
        )
        assert cell_ids(plan) == snapshot(["a", "new", "b", "c"])

    def test_add_before(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [
                _AddOp(
                    cell_id=CellId_t("new"),
                    code="x",
                    config=CellConfig(),
                    before=CellId_t("b"),
                )
            ],
        )
        assert cell_ids(plan) == snapshot(["a", "new", "b", "c"])

    def test_add_into_empty(self) -> None:
        plan = _build_plan(
            [],
            [_AddOp(cell_id=CellId_t("new"), code="x", config=CellConfig())],
        )
        assert cell_ids(plan) == snapshot(["new"])

    def test_add_multiple(self) -> None:
        plan = _build_plan(
            ids("a"),
            [
                _AddOp(cell_id=CellId_t("x"), code="1", config=CellConfig()),
                _AddOp(cell_id=CellId_t("y"), code="2", config=CellConfig()),
            ],
        )
        assert cell_ids(plan) == snapshot(["a", "x", "y"])

    def test_add_after_pending(self) -> None:
        """An add can reference a cell added earlier in the same batch."""
        plan = _build_plan(
            ids("a"),
            [
                _AddOp(cell_id=CellId_t("x"), code="1", config=CellConfig()),
                _AddOp(
                    cell_id=CellId_t("y"),
                    code="2",
                    config=CellConfig(),
                    after=CellId_t("x"),
                ),
            ],
        )
        assert cell_ids(plan) == snapshot(["a", "x", "y"])


class TestUpdate:
    def test_update_code(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [_UpdateOp(cell_id=CellId_t("b"), code="new")],
        )
        assert cell_ids(plan) == snapshot(["a", "b", "c"])
        assert codes(plan) == snapshot([None, "new", None])

    def test_update_config_only(self) -> None:
        cfg = CellConfig(hide_code=True)
        plan = _build_plan(
            ids("a"),
            [_UpdateOp(cell_id=CellId_t("a"), config=cfg)],
        )
        assert plan[0].config == cfg
        assert plan[0].code is None

    def test_update_not_found(self) -> None:
        with pytest.raises(KeyError):
            _build_plan(
                ids("a"),
                [_UpdateOp(cell_id=CellId_t("missing"), code="x")],
            )


class TestDelete:
    def test_delete_single(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [_DeleteOp(cell_id=CellId_t("b"))],
        )
        assert cell_ids(plan) == snapshot(["a", "c"])

    def test_delete_multiple(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [
                _DeleteOp(cell_id=CellId_t("a")),
                _DeleteOp(cell_id=CellId_t("c")),
            ],
        )
        assert cell_ids(plan) == snapshot(["b"])

    def test_delete_all(self) -> None:
        plan = _build_plan(
            ids("a", "b"),
            [
                _DeleteOp(cell_id=CellId_t("a")),
                _DeleteOp(cell_id=CellId_t("b")),
            ],
        )
        assert cell_ids(plan) == snapshot([])

    def test_delete_not_found(self) -> None:
        with pytest.raises(KeyError):
            _build_plan(ids("a"), [_DeleteOp(cell_id=CellId_t("missing"))])


class TestMove:
    def test_move_after(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [_MoveOp(cell_id=CellId_t("a"), after=CellId_t("c"))],
        )
        assert cell_ids(plan) == snapshot(["b", "c", "a"])

    def test_move_before(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [_MoveOp(cell_id=CellId_t("c"), before=CellId_t("a"))],
        )
        assert cell_ids(plan) == snapshot(["c", "a", "b"])

    def test_move_no_anchor_raises(self) -> None:
        with pytest.raises(ValueError, match="before or after"):
            _build_plan(
                ids("a", "b"),
                [_MoveOp(cell_id=CellId_t("a"))],
            )


class TestCombined:
    def test_delete_then_add(self) -> None:
        plan = _build_plan(
            ids("a", "b", "c"),
            [
                _DeleteOp(cell_id=CellId_t("b")),
                _AddOp(
                    cell_id=CellId_t("new"),
                    code="d",
                    config=CellConfig(),
                    after=CellId_t("a"),
                ),
            ],
        )
        assert cell_ids(plan) == snapshot(["a", "new", "c"])

    def test_add_then_update(self) -> None:
        plan = _build_plan(
            ids("a"),
            [
                _AddOp(
                    cell_id=CellId_t("new"), code="tmp", config=CellConfig()
                ),
                _UpdateOp(cell_id=CellId_t("new"), code="final"),
            ],
        )
        assert cell_ids(plan) == snapshot(["a", "new"])
        assert codes(plan) == snapshot([None, "final"])


class TestValidation:
    def test_delete_and_update_same_cell(self) -> None:
        with pytest.raises(ValueError, match="delete.*update"):
            _validate_ops(
                [
                    _UpdateOp(cell_id=CellId_t("a"), code="x"),
                    _DeleteOp(cell_id=CellId_t("a")),
                ]
            )

    def test_update_and_delete_same_cell(self) -> None:
        with pytest.raises(ValueError, match="update.*delete"):
            _validate_ops(
                [
                    _DeleteOp(cell_id=CellId_t("a")),
                    _UpdateOp(cell_id=CellId_t("a"), code="x"),
                ]
            )

    def test_delete_and_move_same_cell(self) -> None:
        with pytest.raises(ValueError, match="delete.*move"):
            _validate_ops(
                [
                    _MoveOp(cell_id=CellId_t("a"), after=CellId_t("b")),
                    _DeleteOp(cell_id=CellId_t("a")),
                ]
            )

    def test_double_delete(self) -> None:
        with pytest.raises(ValueError, match="deleted more than once"):
            _validate_ops(
                [
                    _DeleteOp(cell_id=CellId_t("a")),
                    _DeleteOp(cell_id=CellId_t("a")),
                ]
            )

    def test_valid_ops_pass(self) -> None:
        # Should not raise.
        _validate_ops(
            [
                _AddOp(cell_id=CellId_t("new"), code="x", config=CellConfig()),
                _UpdateOp(cell_id=CellId_t("a"), code="y"),
                _DeleteOp(cell_id=CellId_t("b")),
            ]
        )
