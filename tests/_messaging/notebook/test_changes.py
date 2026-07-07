# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest
from msgspec.structs import replace as structs_replace

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    MoveCell,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
)
from marimo._types.ids import CellId_t


class TestChangesFrozen:
    """All change types must be immutable."""

    def test_create_cell_frozen(self) -> None:
        op = CreateCell(
            cell_id=CellId_t("a"), code="x", name="__", config=CellConfig()
        )
        with pytest.raises(AttributeError):
            op.code = "y"  # type: ignore[misc]

    def test_delete_cell_frozen(self) -> None:
        op = DeleteCell(cell_id=CellId_t("a"))
        with pytest.raises(AttributeError):
            op.cell_id = CellId_t("b")  # type: ignore[misc]

    def test_move_cell_frozen(self) -> None:
        op = MoveCell(cell_id=CellId_t("a"), after=CellId_t("b"))
        with pytest.raises(AttributeError):
            op.after = CellId_t("c")  # type: ignore[misc]

    def test_set_code_frozen(self) -> None:
        op = SetCode(cell_id=CellId_t("a"), code="x")
        with pytest.raises(AttributeError):
            op.code = "y"  # type: ignore[misc]

    def test_set_name_frozen(self) -> None:
        op = SetName(cell_id=CellId_t("a"), name="foo")
        with pytest.raises(AttributeError):
            op.name = "bar"  # type: ignore[misc]

    def test_set_config_frozen(self) -> None:
        op = SetConfig(
            cell_id=CellId_t("a"),
            column=None,
            disabled=False,
            hide_code=True,
        )
        with pytest.raises(AttributeError):
            op.hide_code = False  # type: ignore[misc]

    def test_reorder_cells_frozen(self) -> None:
        op = ReorderCells(cell_ids=(CellId_t("a"), CellId_t("b")))
        with pytest.raises(AttributeError):
            op.cell_ids = ()  # type: ignore[misc]


class TestTransaction:
    def test_creation(self) -> None:
        tx = Transaction(
            changes=(SetCode(cell_id=CellId_t("a"), code="x"),),
            source="kernel",
        )
        assert tx.source == "kernel"
        assert tx.version is None
        assert len(tx.changes) == 1

    def test_frozen(self) -> None:
        tx = Transaction(changes=(), source="test")
        with pytest.raises(AttributeError):
            tx.source = "other"  # type: ignore[misc]

    def test_version_stamping(self) -> None:
        tx = Transaction(changes=(), source="test")
        stamped = structs_replace(tx, version=42)
        assert stamped.version == 42
        assert tx.version is None  # original unchanged

    def test_changes_is_tuple(self) -> None:
        tx = Transaction(
            changes=(
                SetCode(cell_id=CellId_t("a"), code="x"),
                SetName(cell_id=CellId_t("a"), name="foo"),
            ),
            source="test",
        )
        assert isinstance(tx.changes, tuple)
