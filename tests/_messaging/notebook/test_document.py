# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest
from inline_snapshot import snapshot

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    DocumentChange,
    MoveCell,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
)
from marimo._messaging.notebook.document import NotebookCell, NotebookDocument
from marimo._types.ids import CellId_t

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _cell(name: str) -> NotebookCell:
    return NotebookCell(
        id=CellId_t(name), code="", name="__", config=CellConfig()
    )


def _doc(*names: str) -> NotebookDocument:
    return NotebookDocument([_cell(n) for n in names])


def _tx(*changes: DocumentChange, source: str = "test") -> Transaction:
    return Transaction(changes=changes, source=source)


def _ids(doc: NotebookDocument) -> list[str]:
    return [str(cid) for cid in doc.cell_ids]


# ------------------------------------------------------------------
# CreateCell
# ------------------------------------------------------------------


class TestCreateCell:
    def test_append_at_end(self) -> None:
        doc = _doc("a", "b")
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="x",
                    name="__",
                    config=CellConfig(),
                )
            )
        )
        assert _ids(doc) == snapshot(["a", "b", "new"])

    def test_insert_after(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="x",
                    name="__",
                    config=CellConfig(),
                    after=CellId_t("a"),
                )
            )
        )
        assert _ids(doc) == snapshot(["a", "new", "b", "c"])

    def test_insert_before(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="x",
                    name="__",
                    config=CellConfig(),
                    before=CellId_t("b"),
                )
            )
        )
        assert _ids(doc) == snapshot(["a", "new", "b", "c"])

    def test_insert_into_empty(self) -> None:
        doc = _doc()
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="x",
                    name="__",
                    config=CellConfig(),
                )
            )
        )
        assert _ids(doc) == snapshot(["new"])

    def test_multiple(self) -> None:
        doc = _doc("a")
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("x"),
                    code="1",
                    name="__",
                    config=CellConfig(),
                ),
                CreateCell(
                    cell_id=CellId_t("y"),
                    code="2",
                    name="__",
                    config=CellConfig(),
                ),
            )
        )
        assert _ids(doc) == snapshot(["a", "x", "y"])

    def test_after_pending(self) -> None:
        """A create can reference a cell added earlier in the same tx."""
        doc = _doc("a")
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("x"),
                    code="1",
                    name="__",
                    config=CellConfig(),
                ),
                CreateCell(
                    cell_id=CellId_t("y"),
                    code="2",
                    name="__",
                    config=CellConfig(),
                    after=CellId_t("x"),
                ),
            )
        )
        assert _ids(doc) == snapshot(["a", "x", "y"])

    def test_duplicate_id_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(ValueError, match="already exists"):
            doc.apply(
                _tx(
                    CreateCell(
                        cell_id=CellId_t("a"),
                        code="x",
                        name="__",
                        config=CellConfig(),
                    )
                )
            )

    def test_stores_code_and_config(self) -> None:
        doc = _doc()
        cfg = CellConfig(hide_code=True, disabled=True)
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("a"),
                    code="import os",
                    name="imports",
                    config=cfg,
                )
            )
        )
        cell = doc.get_cell(CellId_t("a"))
        assert cell.code == "import os"
        assert cell.name == "imports"
        assert cell.config.hide_code is True
        assert cell.config.disabled is True


# ------------------------------------------------------------------
# DeleteCell
# ------------------------------------------------------------------


class TestDeleteCell:
    def test_delete_single(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(_tx(DeleteCell(cell_id=CellId_t("b"))))
        assert _ids(doc) == snapshot(["a", "c"])

    def test_delete_multiple(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(
            _tx(
                DeleteCell(cell_id=CellId_t("a")),
                DeleteCell(cell_id=CellId_t("c")),
            )
        )
        assert _ids(doc) == snapshot(["b"])

    def test_delete_all(self) -> None:
        doc = _doc("a", "b")
        doc.apply(
            _tx(
                DeleteCell(cell_id=CellId_t("a")),
                DeleteCell(cell_id=CellId_t("b")),
            )
        )
        assert _ids(doc) == snapshot([])

    def test_delete_not_found(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError):
            doc.apply(_tx(DeleteCell(cell_id=CellId_t("missing"))))


# ------------------------------------------------------------------
# MoveCell
# ------------------------------------------------------------------


class TestMoveCell:
    def test_move_after(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(_tx(MoveCell(cell_id=CellId_t("a"), after=CellId_t("c"))))
        assert _ids(doc) == snapshot(["b", "c", "a"])

    def test_move_before(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(_tx(MoveCell(cell_id=CellId_t("c"), before=CellId_t("a"))))
        assert _ids(doc) == snapshot(["c", "a", "b"])

    def test_no_anchor_raises(self) -> None:
        doc = _doc("a", "b")
        with pytest.raises(ValueError, match="before.*after"):
            doc.apply(_tx(MoveCell(cell_id=CellId_t("a"))))


# ------------------------------------------------------------------
# SetCode
# ------------------------------------------------------------------


class TestSetCode:
    def test_update_code(self) -> None:
        doc = _doc("a", "b")
        doc.apply(_tx(SetCode(cell_id=CellId_t("b"), code="new")))
        assert doc.get_cell(CellId_t("b")).code == "new"
        assert doc.get_cell(CellId_t("a")).code == ""  # unchanged

    def test_not_found(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError):
            doc.apply(_tx(SetCode(cell_id=CellId_t("missing"), code="x")))


# ------------------------------------------------------------------
# SetName
# ------------------------------------------------------------------


class TestSetName:
    def test_update_name(self) -> None:
        doc = _doc("a")
        doc.apply(_tx(SetName(cell_id=CellId_t("a"), name="my_cell")))
        assert doc.get_cell(CellId_t("a")).name == "my_cell"


# ------------------------------------------------------------------
# SetConfig
# ------------------------------------------------------------------


class TestSetConfig:
    def test_sets_hide_code(self) -> None:
        doc = _doc("a")
        doc.apply(
            _tx(
                SetConfig(
                    cell_id=CellId_t("a"),
                    column=None,
                    disabled=False,
                    hide_code=True,
                )
            )
        )
        cfg = doc.get_cell(CellId_t("a")).config
        assert cfg == CellConfig(column=None, disabled=False, hide_code=True)

    def test_sets_disabled(self) -> None:
        doc = _doc("a")
        doc.apply(
            _tx(
                SetConfig(
                    cell_id=CellId_t("a"),
                    column=None,
                    disabled=True,
                    hide_code=False,
                )
            )
        )
        cfg = doc.get_cell(CellId_t("a")).config
        assert cfg == CellConfig(column=None, disabled=True, hide_code=False)

    def test_replaces_existing(self) -> None:
        # SetConfig is a full replacement: prior fields are overwritten,
        # not merged. This is what makes ``column=None`` a meaningful reset
        # rather than a sentinel for "leave unchanged".
        doc = NotebookDocument(
            [
                NotebookCell(
                    id=CellId_t("a"),
                    code="",
                    name="__",
                    config=CellConfig(column=2, disabled=True, hide_code=True),
                )
            ]
        )
        doc.apply(
            _tx(
                SetConfig(
                    cell_id=CellId_t("a"),
                    column=0,
                    disabled=False,
                    hide_code=False,
                )
            )
        )
        cfg = doc.get_cell(CellId_t("a")).config
        assert cfg == CellConfig(column=0, disabled=False, hide_code=False)

    def test_column_reset_to_none(self) -> None:
        doc = NotebookDocument(
            [
                NotebookCell(
                    id=CellId_t("a"),
                    code="",
                    name="__",
                    config=CellConfig(column=1),
                )
            ]
        )
        doc.apply(
            _tx(
                SetConfig(
                    cell_id=CellId_t("a"),
                    column=None,
                    disabled=False,
                    hide_code=False,
                )
            )
        )
        assert doc.get_cell(CellId_t("a")).config.column is None


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


class TestValidation:
    def test_delete_and_set_code_same_cell(self) -> None:
        doc = _doc("a")
        with pytest.raises(ValueError, match="delete.*update"):
            doc.apply(
                _tx(
                    SetCode(cell_id=CellId_t("a"), code="x"),
                    DeleteCell(cell_id=CellId_t("a")),
                )
            )

    def test_set_code_and_delete_same_cell(self) -> None:
        doc = _doc("a")
        with pytest.raises(ValueError, match="update.*delete"):
            doc.apply(
                _tx(
                    DeleteCell(cell_id=CellId_t("a")),
                    SetCode(cell_id=CellId_t("a"), code="x"),
                )
            )

    def test_delete_and_move_same_cell(self) -> None:
        doc = _doc("a", "b")
        with pytest.raises(ValueError, match="delete.*move"):
            doc.apply(
                _tx(
                    MoveCell(cell_id=CellId_t("a"), after=CellId_t("b")),
                    DeleteCell(cell_id=CellId_t("a")),
                )
            )

    def test_double_delete(self) -> None:
        doc = _doc("a")
        with pytest.raises(ValueError, match="deleted more than once"):
            doc.apply(
                _tx(
                    DeleteCell(cell_id=CellId_t("a")),
                    DeleteCell(cell_id=CellId_t("a")),
                )
            )

    def test_valid_mixed_ops(self) -> None:
        doc = _doc("a", "b")
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="x",
                    name="__",
                    config=CellConfig(),
                ),
                SetCode(cell_id=CellId_t("a"), code="y"),
                DeleteCell(cell_id=CellId_t("b")),
            )
        )
        assert _ids(doc) == snapshot(["a", "new"])


# ------------------------------------------------------------------
# Versioning
# ------------------------------------------------------------------


class TestVersion:
    def test_increments_on_apply(self) -> None:
        doc = _doc("a")
        assert doc.version == 0
        doc.apply(_tx(SetCode(cell_id=CellId_t("a"), code="x")))
        assert doc.version == 1
        doc.apply(_tx(SetCode(cell_id=CellId_t("a"), code="y")))
        assert doc.version == 2

    def test_stamped_on_returned_tx(self) -> None:
        doc = _doc("a")
        tx = _tx(SetCode(cell_id=CellId_t("a"), code="x"))
        assert tx.version is None
        applied = doc.apply(tx)
        assert applied.version == 1

    def test_empty_tx_no_increment(self) -> None:
        doc = _doc("a")
        doc.apply(_tx(SetCode(cell_id=CellId_t("a"), code="x")))
        assert doc.version == 1
        applied = doc.apply(_tx())
        assert doc.version == 1
        assert applied.version == 1

    def test_replace_cells_bumps_version(self) -> None:
        doc = _doc("a", "b")
        starting = doc.version
        doc._replace_cells([_cell("c"), _cell("d")])
        assert doc.version == starting + 1

    def test_replace_cells_preserves_document_identity(self) -> None:
        doc = _doc("a")
        new_cells = [_cell("b"), _cell("c")]
        doc._replace_cells(new_cells)
        assert _ids(doc) == ["b", "c"]
        # Reassigning the cells list — not mutating in place — lets prior
        # holders (e.g. file-watch diff path) keep a snapshot of the
        # pre-rebuild state for comparison.
        assert doc._cells is new_cells

    def test_rekey_bumps_version(self) -> None:
        doc = _doc("a", "b")
        starting = doc.version
        doc._rekey({CellId_t("a"): CellId_t("x")})
        assert doc.version == starting + 1
        assert _ids(doc) == ["x", "b"]


class TestRekey:
    def test_renames_mapped_cells(self) -> None:
        doc = _doc("a", "b", "c")
        doc._rekey(
            {CellId_t("a"): CellId_t("x"), CellId_t("c"): CellId_t("z")}
        )
        assert _ids(doc) == ["x", "b", "z"]

    def test_preserves_unmapped_cells(self) -> None:
        doc = _doc("a", "b")
        doc._rekey({CellId_t("a"): CellId_t("x")})
        assert _ids(doc) == ["x", "b"]

    def test_rejects_duplicate_target_ids(self) -> None:
        doc = _doc("a", "b")
        with pytest.raises(ValueError, match="duplicate"):
            doc._rekey(
                {CellId_t("a"): CellId_t("x"), CellId_t("b"): CellId_t("x")}
            )

    def test_rejects_target_colliding_with_unmapped(self) -> None:
        doc = _doc("a", "b")
        with pytest.raises(ValueError, match="duplicate"):
            doc._rekey({CellId_t("a"): CellId_t("b")})

    def test_failed_validation_does_not_mutate(self) -> None:
        doc = _doc("a", "b")
        starting = doc.version
        with pytest.raises(ValueError):
            doc._rekey({CellId_t("a"): CellId_t("b")})
        assert _ids(doc) == ["a", "b"]
        assert doc.version == starting


# ------------------------------------------------------------------
# Combined ops
# ------------------------------------------------------------------


class TestCombined:
    def test_delete_then_create(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(
            _tx(
                DeleteCell(cell_id=CellId_t("b")),
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="d",
                    name="__",
                    config=CellConfig(),
                    after=CellId_t("a"),
                ),
            )
        )
        assert _ids(doc) == snapshot(["a", "new", "c"])

    def test_create_then_set_code(self) -> None:
        doc = _doc("a")
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="tmp",
                    name="__",
                    config=CellConfig(),
                ),
                SetCode(cell_id=CellId_t("new"), code="final"),
            )
        )
        assert _ids(doc) == snapshot(["a", "new"])
        assert doc.get_cell(CellId_t("new")).code == "final"

    def test_create_then_move(self) -> None:
        doc = _doc("a", "b")
        doc.apply(
            _tx(
                CreateCell(
                    cell_id=CellId_t("new"),
                    code="x",
                    name="__",
                    config=CellConfig(),
                ),
                MoveCell(cell_id=CellId_t("new"), before=CellId_t("a")),
            )
        )
        assert _ids(doc) == snapshot(["new", "a", "b"])

    def test_source_preserved(self) -> None:
        doc = _doc("a")
        applied = doc.apply(
            _tx(
                SetCode(cell_id=CellId_t("a"), code="x"),
                source="kernel",
            )
        )
        assert applied.source == "kernel"


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------


class TestInit:
    def test_from_cells(self) -> None:
        doc = _doc("a", "b", "c")
        assert _ids(doc) == ["a", "b", "c"]

    def test_empty(self) -> None:
        doc = NotebookDocument()
        assert _ids(doc) == []
        assert doc.version == 0

    def test_get_cell(self) -> None:
        doc = _doc("a", "b")
        cell = doc.get_cell(CellId_t("b"))
        assert cell.id == CellId_t("b")

    def test_get_cell_not_found(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError):
            doc.get_cell(CellId_t("missing"))

    def test_get_returns_none(self) -> None:
        doc = _doc("a")
        assert doc.get(CellId_t("missing")) is None
        assert doc.get(CellId_t("a")) is not None

    def test_contains(self) -> None:
        doc = _doc("a", "b")
        assert CellId_t("a") in doc
        assert CellId_t("missing") not in doc

    def test_len(self) -> None:
        assert len(_doc()) == 0
        assert len(_doc("a", "b")) == 2

    def test_iter(self) -> None:
        doc = _doc("a", "b", "c")
        assert list(doc) == [CellId_t("a"), CellId_t("b"), CellId_t("c")]

    def test_repr(self) -> None:
        doc = _doc("a")
        assert "NotebookDocument(1 cells)" in repr(doc)


# ------------------------------------------------------------------
# NotebookCell.__repr__
# ------------------------------------------------------------------


class TestNotebookCellRepr:
    def test_simple(self) -> None:
        cell = NotebookCell(
            id=CellId_t("abc"), code="x = 1", name="", config=CellConfig()
        )
        assert repr(cell) == "NotebookCell(id='abc', code='x = 1')"

    def test_with_name(self) -> None:
        cell = NotebookCell(
            id=CellId_t("abc"),
            code="x = 1",
            name="my_cell",
            config=CellConfig(),
        )
        assert repr(cell) == (
            "NotebookCell(id='abc', name='my_cell', code='x = 1')"
        )

    def test_multiline_shows_first_line_with_ellipsis(self) -> None:
        cell = NotebookCell(
            id=CellId_t("a"),
            code="line1\nline2\nline3",
            name="",
            config=CellConfig(),
        )
        r = repr(cell)
        assert "line1..." in r
        assert "line2" not in r

    def test_long_first_line_truncated(self) -> None:
        long_code = "x = " + "a" * 100
        cell = NotebookCell(
            id=CellId_t("a"), code=long_code, name="", config=CellConfig()
        )
        r = repr(cell)
        assert "..." in r
        assert long_code[:80] in r

    def test_empty_code(self) -> None:
        cell = NotebookCell(
            id=CellId_t("a"), code="", name="", config=CellConfig()
        )
        assert repr(cell) == "NotebookCell(id='a', code='')"


# ------------------------------------------------------------------
# ReorderCells
# ------------------------------------------------------------------


class TestReorderCells:
    def test_reorder(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(
            _tx(
                ReorderCells(
                    cell_ids=(CellId_t("c"), CellId_t("a"), CellId_t("b"))
                )
            )
        )
        assert _ids(doc) == snapshot(["c", "a", "b"])

    def test_missing_ids_appended(self) -> None:
        """Cells not in the reorder list are appended at the end."""
        doc = _doc("a", "b", "c")
        doc.apply(_tx(ReorderCells(cell_ids=(CellId_t("c"), CellId_t("a")))))
        assert _ids(doc) == snapshot(["c", "a", "b"])

    def test_unknown_ids_ignored(self) -> None:
        """IDs not in the document are silently skipped."""
        doc = _doc("a", "b")
        doc.apply(
            _tx(
                ReorderCells(
                    cell_ids=(
                        CellId_t("b"),
                        CellId_t("unknown"),
                        CellId_t("a"),
                    )
                )
            )
        )
        assert _ids(doc) == snapshot(["b", "a"])

    def test_reorder_single(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(_tx(ReorderCells(cell_ids=(CellId_t("b"),))))
        assert _ids(doc) == snapshot(["b", "a", "c"])
