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
from marimo._messaging.notebook.reconcile import reconcile_transaction
from marimo._types.ids import CellId_t


def _doc(*ids: str) -> NotebookDocument:
    return NotebookDocument(
        [
            NotebookCell(CellId_t(i), code="", name="__", config=CellConfig())
            for i in ids
        ]
    )


def _create(
    cell_id: str, *, before: str | None = None, after: str | None = None
) -> CreateCell:
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
        sanitized = reconcile_transaction(changes, doc)
        assert sanitized == changes


class TestCreateAnchor:
    def test_missing_after_anchor_is_stripped_and_appended(self) -> None:
        doc = _doc("a")
        sanitized = reconcile_transaction(
            (_create("new", after="ghost"),), doc
        )

        (result,) = sanitized
        assert isinstance(result, CreateCell)
        assert result.cell_id == CellId_t("new")
        assert result.after is None
        assert result.before is None

    def test_missing_before_anchor_is_stripped_and_appended(self) -> None:
        doc = _doc("a")
        sanitized = reconcile_transaction(
            (_create("new", before="ghost"),), doc
        )

        (result,) = sanitized
        assert isinstance(result, CreateCell)
        assert result.before is None
        assert result.after is None

    def test_anchor_created_earlier_in_batch_is_kept(self) -> None:
        doc = _doc("a")
        changes = (
            _create("x", after="a"),
            _create("y", after="x"),
        )
        sanitized = reconcile_transaction(changes, doc)
        assert sanitized == changes


class TestCreateDuplicate:
    def test_create_of_existing_id_is_dropped(self) -> None:
        doc = _doc("a", "b")
        sanitized = reconcile_transaction((_create("a", after="b"),), doc)
        assert sanitized == ()


class TestDelete:
    def test_delete_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a")
        sanitized = reconcile_transaction(
            (DeleteCell(cell_id=CellId_t("ghost")),), doc
        )
        assert sanitized == ()

    def test_recreate_of_deleted_existing_id_is_dropped(self) -> None:
        doc = _doc("a")
        delete = DeleteCell(cell_id=CellId_t("a"))
        sanitized = reconcile_transaction((delete, _create("a")), doc)
        assert sanitized == (delete,)

    def test_recreate_of_batch_created_id_is_dropped(self) -> None:
        doc = _doc("a")
        create = _create("x", after="a")
        delete = DeleteCell(cell_id=CellId_t("x"))
        sanitized = reconcile_transaction((create, delete, _create("x")), doc)
        assert sanitized == (create, delete)


class TestSetProperties:
    def test_set_code_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a")
        sanitized = reconcile_transaction(
            (SetCode(cell_id=CellId_t("ghost"), code="x = 1"),), doc
        )
        assert sanitized == ()

    def test_set_name_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a")
        sanitized = reconcile_transaction(
            (SetName(cell_id=CellId_t("ghost"), name="renamed"),), doc
        )
        assert sanitized == ()

    def test_set_config_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a")
        sanitized = reconcile_transaction(
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

    def test_set_code_of_present_cell_is_kept(self) -> None:
        doc = _doc("a")
        change = SetCode(cell_id=CellId_t("a"), code="x = 1")
        sanitized = reconcile_transaction((change,), doc)
        assert sanitized == (change,)


class TestMove:
    def test_move_of_missing_cell_is_dropped(self) -> None:
        doc = _doc("a", "b")
        sanitized = reconcile_transaction(
            (MoveCell(cell_id=CellId_t("ghost"), after=CellId_t("a")),), doc
        )
        assert sanitized == ()

    def test_move_with_missing_anchor_is_dropped(self) -> None:
        doc = _doc("a", "b")
        sanitized = reconcile_transaction(
            (MoveCell(cell_id=CellId_t("a"), after=CellId_t("ghost")),), doc
        )
        assert sanitized == ()

    def test_move_with_live_anchor_is_kept(self) -> None:
        doc = _doc("a", "b")
        change = MoveCell(cell_id=CellId_t("a"), after=CellId_t("b"))
        sanitized = reconcile_transaction((change,), doc)
        assert sanitized == (change,)

    def test_move_with_no_anchor_is_dropped(self) -> None:
        doc = _doc("a", "b")
        sanitized = reconcile_transaction(
            (MoveCell(cell_id=CellId_t("a"), after=None, before=None),), doc
        )
        assert sanitized == ()

    def test_move_anchored_to_itself_is_dropped(self) -> None:
        doc = _doc("a", "b")
        sanitized = reconcile_transaction(
            (MoveCell(cell_id=CellId_t("a"), after=CellId_t("a")),), doc
        )
        assert sanitized == ()


class TestReorder:
    def test_reorder_passes_through_untouched(self) -> None:
        doc = _doc("a", "b")
        change = ReorderCells(
            cell_ids=(CellId_t("b"), CellId_t("a"), CellId_t("ghost"))
        )
        sanitized = reconcile_transaction((change,), doc)
        assert sanitized == (change,)


class TestOrderPreserved:
    def test_surviving_changes_keep_input_order(self) -> None:
        doc = _doc("a", "b")
        changes = (
            SetCode(cell_id=CellId_t("a"), code="1"),
            DeleteCell(cell_id=CellId_t("ghost")),
            SetCode(cell_id=CellId_t("b"), code="2"),
        )
        sanitized = reconcile_transaction(changes, doc)
        assert sanitized == (changes[0], changes[2])
