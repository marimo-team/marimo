# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    MoveCell,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
)
from marimo._messaging.notebook.document import (
    NotebookCell,
    NotebookDocument,
)
from marimo._messaging.notebook.reconcile import (
    reconcile_transaction,
)
from marimo._types.ids import CellId_t


def _doc(*ids: str) -> NotebookDocument:
    return NotebookDocument(
        [
            NotebookCell(CellId_t(i), code="", name="__", config=CellConfig())
            for i in ids
        ]
    )


def _create(cell_id: str, *, before: str | None = None, after: str | None = None) -> CreateCell:
    return CreateCell(
        cell_id=CellId_t(cell_id),
        code="",
        name="__",
        config=CellConfig(),
        before=CellId_t(before) if before is not None else None,
        after=CellId_t(after) if after is not None else None,
    )


class TestCleanTransaction:
    def test_clean_batch_unchanged(self) -> None:
        doc = _doc("a", "b")
        changes = (
            SetCode(cell_id=CellId_t("a"), code="x = 1"),
            _create("c", after="b"),
            DeleteCell(cell_id=CellId_t("b")),
        )
        sanitized, repairs = reconcile_transaction(changes, doc)
        assert sanitized == changes
        assert repairs == []


class TestCreateAnchor:
    def test_missing_after_anchor_is_stripped_and_appended(self) -> None:
        doc = _doc("a")
        (change,) = (_create("new", after="ghost"),)
        sanitized, repairs = reconcile_transaction((change,), doc)

        assert len(sanitized) == 1
        (result,) = sanitized
        assert isinstance(result, CreateCell)
        assert result.cell_id == CellId_t("new")
        assert result.after is None
        assert result.before is None

        assert len(repairs) == 1
        (repair,) = repairs
        assert repair.change_type == "create-cell"
        assert repair.cell_id == CellId_t("new")
        assert repair.reason == "anchor not found"

    def test_missing_before_anchor_is_stripped_and_appended(self) -> None:
        doc = _doc("a")
        sanitized, repairs = reconcile_transaction(
            (_create("new", before="ghost"),), doc
        )

        (result,) = sanitized
        assert isinstance(result, CreateCell)
        assert result.before is None
        assert result.after is None

        (repair,) = repairs
        assert repair.change_type == "create-cell"
        assert repair.reason == "anchor not found"

    def test_anchor_created_earlier_in_batch_is_kept(self) -> None:
        doc = _doc("a")
        changes = (
            _create("x", after="a"),
            _create("y", after="x"),
        )
        sanitized, repairs = reconcile_transaction(changes, doc)
        assert sanitized == changes
        assert repairs == []


class TestCreateDuplicate:
    def test_create_of_existing_id_is_dropped(self) -> None:
        doc = _doc("a", "b")
        sanitized, repairs = reconcile_transaction(
            (_create("a", after="b"),), doc
        )
        assert sanitized == ()
        (repair,) = repairs
        assert repair.change_type == "create-cell"
        assert repair.cell_id == CellId_t("a")
        assert repair.reason == "cell already exists"


class TestDelete:
    def test_delete_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a")
        sanitized, repairs = reconcile_transaction(
            (DeleteCell(cell_id=CellId_t("ghost")),), doc
        )
        assert sanitized == ()
        (repair,) = repairs
        assert repair.change_type == "delete-cell"
        assert repair.cell_id == CellId_t("ghost")
        assert repair.reason == "cell not found"

    def test_delete_then_recreate_resolves_in_batch_order(self) -> None:
        doc = _doc("a")
        changes = (
            DeleteCell(cell_id=CellId_t("a")),
            _create("a"),
        )
        sanitized, repairs = reconcile_transaction(changes, doc)
        assert sanitized == changes
        assert repairs == []


class TestSetProperties:
    def test_set_code_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a")
        sanitized, repairs = reconcile_transaction(
            (SetCode(cell_id=CellId_t("ghost"), code="x = 1"),), doc
        )
        assert sanitized == ()
        (repair,) = repairs
        assert repair.change_type == "set-code"
        assert repair.reason == "cell not found"

    def test_set_name_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a")
        sanitized, repairs = reconcile_transaction(
            (SetName(cell_id=CellId_t("ghost"), name="renamed"),), doc
        )
        assert sanitized == ()
        (repair,) = repairs
        assert repair.change_type == "set-name"
        assert repair.reason == "cell not found"

    def test_set_config_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a")
        sanitized, repairs = reconcile_transaction(
            (
                SetConfig(
                    cell_id=CellId_t("ghost"),
                    column=None,
                    disabled=False,
                    hide_code=False,
                ),
            ),
            doc,
        )
        assert sanitized == ()
        (repair,) = repairs
        assert repair.change_type == "set-config"
        assert repair.reason == "cell not found"

    def test_set_code_of_present_cell_is_kept(self) -> None:
        doc = _doc("a")
        change = SetCode(cell_id=CellId_t("a"), code="x = 1")
        sanitized, repairs = reconcile_transaction((change,), doc)
        assert sanitized == (change,)
        assert repairs == []


class TestMove:
    def test_move_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a", "b")
        sanitized, repairs = reconcile_transaction(
            (MoveCell(cell_id=CellId_t("ghost"), after=CellId_t("a")),), doc
        )
        assert sanitized == ()
        (repair,) = repairs
        assert repair.change_type == "move-cell"
        assert repair.cell_id == CellId_t("ghost")
        assert repair.reason == "cell not found"

    def test_move_with_missing_anchor_is_dropped(self) -> None:
        doc = _doc("a", "b")
        sanitized, repairs = reconcile_transaction(
            (MoveCell(cell_id=CellId_t("a"), after=CellId_t("ghost")),), doc
        )
        assert sanitized == ()
        (repair,) = repairs
        assert repair.change_type == "move-cell"
        assert repair.cell_id == CellId_t("a")
        assert repair.reason == "anchor not found"

    def test_move_with_live_anchor_is_kept(self) -> None:
        doc = _doc("a", "b")
        change = MoveCell(cell_id=CellId_t("a"), after=CellId_t("b"))
        sanitized, repairs = reconcile_transaction((change,), doc)
        assert sanitized == (change,)
        assert repairs == []


class TestReorder:
    def test_reorder_passes_through_untouched(self) -> None:
        doc = _doc("a", "b")
        change = ReorderCells(
            cell_ids=(CellId_t("b"), CellId_t("a"), CellId_t("ghost"))
        )
        sanitized, repairs = reconcile_transaction((change,), doc)
        assert sanitized == (change,)
        assert repairs == []


class TestOrderPreserved:
    def test_surviving_changes_keep_input_order(self) -> None:
        doc = _doc("a", "b")
        changes = (
            SetCode(cell_id=CellId_t("a"), code="1"),
            DeleteCell(cell_id=CellId_t("ghost")),
            SetCode(cell_id=CellId_t("b"), code="2"),
        )
        sanitized, repairs = reconcile_transaction(changes, doc)
        assert sanitized == (changes[0], changes[2])
        assert len(repairs) == 1
