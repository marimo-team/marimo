# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._ast.cell import CellConfig
from marimo._session.state.document import (
    CellCreated,
    CellDeleted,
    CellMoved,
    CellsReordered,
    CodeChanged,
    ConfigChanged,
    DocumentCell,
    NameChanged,
    NotebookDocument,
)


def _doc(*codes: str) -> NotebookDocument:
    """Helper: build a document from (id, code) pairs.

    Cell IDs are "0", "1", "2", ... matching their initial position.
    """
    cells = [DocumentCell(id=str(i), code=c) for i, c in enumerate(codes)]
    return NotebookDocument(cells)


def _ids(doc: NotebookDocument) -> list[str]:
    return list(doc)


# ------------------------------------------------------------------
# Construction
# ------------------------------------------------------------------


class TestConstruction:
    def test_empty(self) -> None:
        doc = NotebookDocument()
        assert len(doc) == 0
        assert _ids(doc) == []

    def test_from_cells(self) -> None:
        doc = _doc("a = 1", "b = 2", "c = 3")
        assert len(doc) == 3
        assert _ids(doc) == ["0", "1", "2"]

    def test_values_iterates_cells(self) -> None:
        doc = _doc("a = 1", "b = 2")
        codes = [c.code for c in doc.values()]
        assert codes == ["a = 1", "b = 2"]

    def test_contains(self) -> None:
        doc = _doc("a = 1")
        assert "0" in doc
        assert "999" not in doc


# ------------------------------------------------------------------
# CellCreated
# ------------------------------------------------------------------


class TestCellCreated:
    def test_append_to_empty(self) -> None:
        doc = NotebookDocument()
        doc.apply(CellCreated(id="a", code="x = 1"))
        assert _ids(doc) == ["a"]
        assert doc["a"].code == "x = 1"

    def test_append_to_end(self) -> None:
        doc = _doc("a", "b")
        doc.apply(CellCreated(id="c", code="new"))
        assert _ids(doc) == ["0", "1", "c"]

    def test_insert_after(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellCreated(id="x", code="new", after="0"))
        assert _ids(doc) == ["0", "x", "1", "2"]

    def test_insert_after_last(self) -> None:
        doc = _doc("a", "b")
        doc.apply(CellCreated(id="x", code="new", after="1"))
        assert _ids(doc) == ["0", "1", "x"]

    def test_with_name_and_config(self) -> None:
        cfg = CellConfig(hide_code=True, disabled=True)
        doc = NotebookDocument()
        doc.apply(CellCreated(id="a", code="x", name="setup", config=cfg))
        cell = doc["a"]
        assert cell.name == "setup"
        assert cell.config.hide_code is True
        assert cell.config.disabled is True

    def test_duplicate_id_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(ValueError, match="already exists"):
            doc.apply(CellCreated(id="0", code="dup"))

    def test_after_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CellCreated(id="x", code="new", after="missing"))


# ------------------------------------------------------------------
# CellDeleted
# ------------------------------------------------------------------


class TestCellDeleted:
    def test_delete_only_cell(self) -> None:
        doc = _doc("a")
        doc.apply(CellDeleted(id="0"))
        assert len(doc) == 0
        assert "0" not in doc

    def test_delete_middle(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellDeleted(id="1"))
        assert _ids(doc) == ["0", "2"]

    def test_delete_first(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellDeleted(id="0"))
        assert _ids(doc) == ["1", "2"]

    def test_delete_last(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellDeleted(id="2"))
        assert _ids(doc) == ["0", "1"]

    def test_delete_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CellDeleted(id="missing"))


# ------------------------------------------------------------------
# CellMoved
# ------------------------------------------------------------------


class TestCellMoved:
    def test_move_to_beginning(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellMoved(id="2", after=None))
        assert _ids(doc) == ["2", "0", "1"]

    def test_move_forward(self) -> None:
        doc = _doc("a", "b", "c", "d")
        doc.apply(CellMoved(id="0", after="2"))
        assert _ids(doc) == ["1", "2", "0", "3"]

    def test_move_backward(self) -> None:
        doc = _doc("a", "b", "c", "d")
        doc.apply(CellMoved(id="3", after="0"))
        assert _ids(doc) == ["0", "3", "1", "2"]

    def test_noop(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellMoved(id="1", after="0"))
        assert _ids(doc) == ["0", "1", "2"]

    def test_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CellMoved(id="missing", after=None))

    def test_after_nonexistent_raises(self) -> None:
        doc = _doc("a", "b")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CellMoved(id="0", after="missing"))


# ------------------------------------------------------------------
# CellsReordered
# ------------------------------------------------------------------


class TestCellsReordered:
    def test_move_to_beginning(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellsReordered(cell_ids=["2", "0", "1"]))
        assert _ids(doc) == ["2", "0", "1"]

    def test_move_forward(self) -> None:
        doc = _doc("a", "b", "c", "d")
        doc.apply(CellsReordered(cell_ids=["1", "2", "0", "3"]))
        assert _ids(doc) == ["1", "2", "0", "3"]

    def test_move_backward(self) -> None:
        doc = _doc("a", "b", "c", "d")
        doc.apply(CellsReordered(cell_ids=["0", "3", "1", "2"]))
        assert _ids(doc) == ["0", "3", "1", "2"]

    def test_same_order_is_noop(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellsReordered(cell_ids=["0", "1", "2"]))
        assert _ids(doc) == ["0", "1", "2"]

    def test_unknown_ids_ignored(self) -> None:
        doc = _doc("a", "b")
        doc.apply(CellsReordered(cell_ids=["1", "unknown", "0"]))
        assert _ids(doc) == ["1", "0"]

    def test_missing_ids_appended(self) -> None:
        """Cells not in the reorder list are appended at the end."""
        doc = _doc("a", "b", "c")
        doc.apply(CellsReordered(cell_ids=["2", "0"]))
        assert _ids(doc) == ["2", "0", "1"]

    def test_preserves_cell_data(self) -> None:
        doc = _doc("code_a", "code_b")
        doc.apply(CellsReordered(cell_ids=["1", "0"]))
        assert doc["0"].code == "code_a"
        assert doc["1"].code == "code_b"


# ------------------------------------------------------------------
# CodeChanged
# ------------------------------------------------------------------


class TestCodeChanged:
    def test_change_code(self) -> None:
        doc = _doc("old code")
        doc.apply(CodeChanged(id="0", code="new code"))
        assert doc["0"].code == "new code"

    def test_preserves_other_fields(self) -> None:
        doc = NotebookDocument(
            [
                DocumentCell(
                    id="a",
                    code="x",
                    name="setup",
                    config=CellConfig(hide_code=True),
                )
            ]
        )
        doc.apply(CodeChanged(id="a", code="y"))
        cell = doc["a"]
        assert cell.code == "y"
        assert cell.name == "setup"
        assert cell.config.hide_code is True

    def test_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CodeChanged(id="missing", code="x"))

    def test_last_write_wins(self) -> None:
        doc = _doc("v1")
        doc.apply(CodeChanged(id="0", code="v2"))
        doc.apply(CodeChanged(id="0", code="v3"))
        assert doc["0"].code == "v3"


# ------------------------------------------------------------------
# NameChanged
# ------------------------------------------------------------------


class TestNameChanged:
    def test_rename(self) -> None:
        doc = _doc("a")
        doc.apply(NameChanged(id="0", name="setup"))
        assert doc["0"].name == "setup"

    def test_clear_name(self) -> None:
        doc = NotebookDocument([DocumentCell(id="a", code="x", name="old")])
        doc.apply(NameChanged(id="a", name=""))
        assert doc["a"].name == ""

    def test_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(NameChanged(id="missing", name="x"))


# ------------------------------------------------------------------
# ConfigChanged
# ------------------------------------------------------------------


class TestConfigChanged:
    def test_change_config(self) -> None:
        doc = _doc("a")
        doc.apply(ConfigChanged(id="0", config=CellConfig(hide_code=True)))
        assert doc["0"].config.hide_code is True

    def test_preserves_code(self) -> None:
        doc = _doc("important code")
        doc.apply(ConfigChanged(id="0", config=CellConfig(disabled=True)))
        assert doc["0"].code == "important code"
        assert doc["0"].config.disabled is True

    def test_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(ConfigChanged(id="missing", config=CellConfig()))


# ------------------------------------------------------------------
# Event sequences
# ------------------------------------------------------------------


class TestEventSequences:
    def test_create_move_edit(self) -> None:
        """Full workflow: create cells, reorder, edit."""
        doc = NotebookDocument()
        doc.apply(CellCreated(id="a", code="import mo"))
        doc.apply(CellCreated(id="b", code="red"))
        doc.apply(CellCreated(id="c", code="green"))
        assert _ids(doc) == ["a", "b", "c"]

        doc.apply(CellsReordered(cell_ids=["c", "a", "b"]))
        assert _ids(doc) == ["c", "a", "b"]

        doc.apply(CodeChanged(id="c", code="green (edited)"))
        assert doc["c"].code == "green (edited)"
        assert _ids(doc) == ["c", "a", "b"]

    def test_create_delete_create(self) -> None:
        """Deleting a cell frees the ID for reuse."""
        doc = NotebookDocument()
        doc.apply(CellCreated(id="a", code="v1"))
        doc.apply(CellDeleted(id="a"))
        doc.apply(CellCreated(id="a", code="v2"))
        assert doc["a"].code == "v2"

    def test_interleaved_frontend_and_agent(self) -> None:
        """Simulate frontend and code_mode interleaving events."""
        doc = NotebookDocument()

        # Agent creates cells
        doc.apply(CellCreated(id="a", code="import mo"))
        doc.apply(CellCreated(id="b", code="red"))
        doc.apply(CellCreated(id="c", code="green"))

        # User drags green to top
        doc.apply(CellsReordered(cell_ids=["c", "a", "b"]))
        assert _ids(doc) == ["c", "a", "b"]

        # Agent edits red — should NOT change ordering
        doc.apply(CodeChanged(id="b", code="red (edited)"))
        assert _ids(doc) == ["c", "a", "b"]
        assert doc["b"].code == "red (edited)"

        # User creates a new cell between green and import
        doc.apply(CellCreated(id="d", code="new", after="c"))
        assert _ids(doc) == ["c", "d", "a", "b"]

        # Agent deletes the new cell
        doc.apply(CellDeleted(id="d"))
        assert _ids(doc) == ["c", "a", "b"]

    def test_multiple_moves(self) -> None:
        doc = _doc("a", "b", "c", "d", "e")

        doc.apply(CellsReordered(cell_ids=["0", "4", "1", "2", "3"]))
        assert _ids(doc) == ["0", "4", "1", "2", "3"]

        doc.apply(CellsReordered(cell_ids=["2", "0", "4", "1", "3"]))
        assert _ids(doc) == ["2", "0", "4", "1", "3"]

    def test_index_consistency_after_many_mutations(self) -> None:
        """The internal index must stay consistent through all operations."""
        doc = NotebookDocument()

        # Build up
        for i in range(10):
            doc.apply(CellCreated(id=str(i), code=f"cell {i}"))

        # Delete evens
        for i in range(0, 10, 2):
            doc.apply(CellDeleted(id=str(i)))
        assert _ids(doc) == ["1", "3", "5", "7", "9"]

        # Move 9 to front
        doc.apply(CellsReordered(cell_ids=["9", "1", "3", "5", "7"]))
        assert _ids(doc) == ["9", "1", "3", "5", "7"]

        # Create new cells in gaps
        doc.apply(CellCreated(id="a", code="new", after="1"))
        doc.apply(CellCreated(id="b", code="new", after="5"))
        assert _ids(doc) == ["9", "1", "a", "3", "5", "b", "7"]

        # Verify every cell is findable
        for cid in _ids(doc):
            assert doc[cid].id == cid
