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
    NameChanged,
    NotebookCell,
    NotebookDocument,
)
from marimo._types.ids import CellId_t


def _doc(*codes: str) -> NotebookDocument:
    """Helper: build a document from (id, code) pairs.

    Cell IDs are "0", "1", "2", ... matching their initial position.
    """
    cells = [
        NotebookCell(id=CellId_t(str(i)), code=c) for i, c in enumerate(codes)
    ]
    return NotebookDocument(cells)


def _ids(doc: NotebookDocument) -> list[CellId_t]:
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
        cid = CellId_t("a")
        doc.apply(CellCreated(id=cid, code="x = 1"))
        assert _ids(doc) == [cid]
        assert doc[cid].code == "x = 1"

    def test_append_to_end(self) -> None:
        doc = _doc("a", "b")
        cid = CellId_t("c")
        doc.apply(CellCreated(id=cid, code="new"))
        assert _ids(doc) == ["0", "1", "c"]

    def test_insert_after(self) -> None:
        doc = _doc("a", "b", "c")
        cid = CellId_t("x")
        target = CellId_t("0")
        doc.apply(CellCreated(id=cid, code="new", after=target))
        assert _ids(doc) == ["0", "x", "1", "2"]

    def test_insert_after_last(self) -> None:
        doc = _doc("a", "b")
        cid = CellId_t("x")
        target = CellId_t("1")
        doc.apply(CellCreated(id=cid, code="new", after=target))
        assert _ids(doc) == ["0", "1", "x"]

    def test_with_name_and_config(self) -> None:
        cfg = CellConfig(hide_code=True, disabled=True)
        cid = CellId_t("CellId")
        doc = NotebookDocument()
        doc.apply(CellCreated(id=cid, code="x", name="setup", config=cfg))
        cell = doc[cid]
        assert cell.name == "setup"
        assert cell.config.hide_code is True
        assert cell.config.disabled is True

    def test_duplicate_id_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(ValueError, match="already exists"):
            doc.apply(CellCreated(id=CellId_t("0"), code="dup"))

    def test_after_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(
                CellCreated(
                    id=CellId_t("x"), code="new", after=CellId_t("missing")
                )
            )


# ------------------------------------------------------------------
# CellDeleted
# ------------------------------------------------------------------


class TestCellDeleted:
    def test_delete_only_cell(self) -> None:
        cid = CellId_t("0")
        doc = _doc("a")
        doc.apply(CellDeleted(id=cid))
        assert len(doc) == 0
        assert cid not in doc

    def test_delete_middle(self) -> None:
        cid = CellId_t("1")
        doc = _doc("a", "b", "c")
        doc.apply(CellDeleted(id=cid))
        assert _ids(doc) == ["0", "2"]

    def test_delete_first(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellDeleted(id=CellId_t("0")))
        assert _ids(doc) == ["1", "2"]

    def test_delete_last(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellDeleted(id=CellId_t("2")))
        assert _ids(doc) == ["0", "1"]

    def test_delete_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CellDeleted(id=CellId_t("missing")))


# ------------------------------------------------------------------
# CellMoved
# ------------------------------------------------------------------


class TestCellMoved:
    def test_move_to_beginning(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellMoved(id=CellId_t("2"), after=None))
        assert _ids(doc) == ["2", "0", "1"]

    def test_move_forward(self) -> None:
        doc = _doc("a", "b", "c", "d")
        doc.apply(CellMoved(id=CellId_t("0"), after=CellId_t("2")))
        assert _ids(doc) == ["1", "2", "0", "3"]

    def test_move_backward(self) -> None:
        doc = _doc("a", "b", "c", "d")
        doc.apply(CellMoved(id=CellId_t("3"), after=CellId_t("0")))
        assert _ids(doc) == ["0", "3", "1", "2"]

    def test_noop(self) -> None:
        doc = _doc("a", "b", "c")
        doc.apply(CellMoved(id=CellId_t("1"), after=CellId_t("0")))
        assert _ids(doc) == ["0", "1", "2"]

    def test_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CellMoved(id=CellId_t("missing"), after=None))

    def test_after_nonexistent_raises(self) -> None:
        doc = _doc("a", "b")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CellMoved(id=CellId_t("0"), after=CellId_t("missing")))


# ------------------------------------------------------------------
# CellsReordered
# ------------------------------------------------------------------


class TestCellsReordered:
    def test_move_to_beginning(self) -> None:
        doc = _doc("a", "b", "c")
        c0, c1, c2 = doc
        doc.apply(CellsReordered(cell_ids=[c2, c0, c1]))
        assert _ids(doc) == ["2", "0", "1"]

    def test_move_forward(self) -> None:
        doc = _doc("a", "b", "c", "d")
        c0, c1, c2, c3 = doc
        doc.apply(CellsReordered(cell_ids=[c1, c2, c0, c3]))
        assert _ids(doc) == ["1", "2", "0", "3"]

    def test_move_backward(self) -> None:
        doc = _doc("a", "b", "c", "d")
        c0, c1, c2, c3 = doc
        doc.apply(CellsReordered(cell_ids=[c0, c3, c1, c2]))
        assert _ids(doc) == ["0", "3", "1", "2"]

    def test_same_order_is_noop(self) -> None:
        doc = _doc("a", "b", "c")
        ids = list(doc)
        doc.apply(CellsReordered(cell_ids=ids))
        assert _ids(doc) == ids

    def test_unknown_ids_ignored(self) -> None:
        doc = _doc("a", "b")
        cid0, cid1 = doc
        doc.apply(CellsReordered(cell_ids=[cid1, CellId_t("unknown"), cid0]))
        assert _ids(doc) == ["1", "0"]

    def test_missing_ids_appended(self) -> None:
        """Cells not in the reorder list are appended at the end."""
        doc = _doc("a", "b", "c")
        cid0, _, cid2 = doc
        doc.apply(CellsReordered(cell_ids=[cid2, cid0]))
        assert _ids(doc) == ["2", "0", "1"]

    def test_preserves_cell_data(self) -> None:
        doc = _doc("code_a", "code_b")
        cid0, cid1 = doc
        doc.apply(CellsReordered(cell_ids=[cid1, cid0]))
        assert doc[cid0].code == "code_a"
        assert doc[cid1].code == "code_b"


# ------------------------------------------------------------------
# CodeChanged
# ------------------------------------------------------------------


class TestCodeChanged:
    def test_change_code(self) -> None:
        doc = _doc("old code")
        cid, *_ = doc
        doc.apply(CodeChanged(id=cid, code="new code"))
        assert doc[cid].code == "new code"

    def test_preserves_other_fields(self) -> None:
        cid = CellId_t("a")
        doc = NotebookDocument(
            [
                NotebookCell(
                    id=cid,
                    code="x",
                    name="setup",
                    config=CellConfig(hide_code=True),
                )
            ]
        )
        doc.apply(CodeChanged(id=cid, code="y"))
        cell = doc[cid]
        assert cell.code == "y"
        assert cell.name == "setup"
        assert cell.config.hide_code is True

    def test_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(CodeChanged(id=CellId_t("missing"), code="x"))

    def test_last_write_wins(self) -> None:
        doc = _doc("v1")
        cid, *_ = doc
        doc.apply(CodeChanged(id=cid, code="v2"))
        doc.apply(CodeChanged(id=cid, code="v3"))
        assert doc[cid].code == "v3"


# ------------------------------------------------------------------
# NameChanged
# ------------------------------------------------------------------


class TestNameChanged:
    def test_rename(self) -> None:
        doc = _doc("a")
        cid, *_ = doc
        doc.apply(NameChanged(id=cid, name="setup"))
        assert doc[cid].name == "setup"

    def test_clear_name(self) -> None:
        cid = CellId_t("a")
        doc = NotebookDocument([NotebookCell(id=cid, code="x", name="old")])
        doc.apply(NameChanged(id=cid, name=""))
        assert doc[cid].name == ""

    def test_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(NameChanged(id=CellId_t("missing"), name="x"))


# ------------------------------------------------------------------
# ConfigChanged
# ------------------------------------------------------------------


class TestConfigChanged:
    def test_change_config(self) -> None:
        doc = _doc("a")
        cid, *_ = doc
        doc.apply(ConfigChanged(id=cid, config=CellConfig(hide_code=True)))
        assert doc[cid].config.hide_code is True

    def test_preserves_code(self) -> None:
        doc = _doc("important code")
        cid, *_ = doc
        doc.apply(ConfigChanged(id=cid, config=CellConfig(disabled=True)))
        assert doc[cid].code == "important code"
        assert doc[cid].config.disabled is True

    def test_nonexistent_raises(self) -> None:
        doc = _doc("a")
        with pytest.raises(KeyError, match="not in document"):
            doc.apply(
                ConfigChanged(id=CellId_t("missing"), config=CellConfig())
            )


# ------------------------------------------------------------------
# Event sequences
# ------------------------------------------------------------------


class TestEventSequences:
    def test_create_move_edit(self) -> None:
        """Full workflow: create cells, reorder, edit."""
        doc = NotebookDocument()

        ca = CellCreated(id=CellId_t("a"), code="import mo")
        doc.apply(ca)
        cb = CellCreated(id=CellId_t("b"), code="red")
        doc.apply(cb)
        cc = CellCreated(id=CellId_t("c"), code="green")
        doc.apply(cc)

        assert _ids(doc) == ["a", "b", "c"]

        doc.apply(CellsReordered(cell_ids=[cc.id, ca.id, cb.id]))
        assert _ids(doc) == ["c", "a", "b"]

        doc.apply(CodeChanged(id=cc.id, code="green (edited)"))
        assert doc[cc.id].code == "green (edited)"
        assert _ids(doc) == ["c", "a", "b"]

    def test_create_delete_create(self) -> None:
        """Deleting a cell frees the ID for reuse."""
        cid = CellId_t("a")
        doc = NotebookDocument()
        doc.apply(CellCreated(id=cid, code="v1"))
        doc.apply(CellDeleted(id=cid))
        doc.apply(CellCreated(id=cid, code="v2"))
        assert doc[cid].code == "v2"

    def test_interleaved_frontend_and_agent(self) -> None:
        """Simulate frontend and code_mode interleaving events."""
        doc = NotebookDocument()

        a, b, c, d = (
            CellId_t("a"),
            CellId_t("b"),
            CellId_t("c"),
            CellId_t("d"),
        )

        # Agent creates cells
        doc.apply(CellCreated(id=a, code="import mo"))
        doc.apply(CellCreated(id=b, code="red"))
        doc.apply(CellCreated(id=c, code="green"))

        # User drags green to top
        doc.apply(CellsReordered(cell_ids=[c, a, b]))
        assert _ids(doc) == [c, a, b]

        # Agent edits red — should NOT change ordering
        doc.apply(CodeChanged(id=b, code="red (edited)"))
        assert _ids(doc) == [c, a, b]
        assert doc[b].code == "red (edited)"

        # User creates a new cell between green and import
        doc.apply(CellCreated(id=d, code="new", after=c))
        assert _ids(doc) == [c, d, a, b]

        # Agent deletes the new cell
        doc.apply(CellDeleted(id=d))
        assert _ids(doc) == [c, a, b]

    def test_multiple_moves(self) -> None:
        doc = _doc("a", "b", "c", "d", "e")
        c0, c1, c2, c3, c4 = doc

        doc.apply(CellsReordered(cell_ids=[c0, c4, c1, c2, c3]))
        assert _ids(doc) == [c0, c4, c1, c2, c3]

        doc.apply(CellsReordered(cell_ids=[c2, c0, c4, c1, c3]))
        assert _ids(doc) == [c2, c0, c4, c1, c3]

    def test_index_consistency_after_many_mutations(self) -> None:
        """The internal index must stay consistent through all operations."""
        doc = NotebookDocument()

        # Build up
        ids = [CellId_t(str(i)) for i in range(10)]
        for i, cid in enumerate(ids):
            doc.apply(CellCreated(id=cid, code=f"cell {i}"))

        # Delete evens
        for i in range(0, 10, 2):
            doc.apply(CellDeleted(id=ids[i]))
        assert _ids(doc) == [ids[1], ids[3], ids[5], ids[7], ids[9]]

        # Move 9 to front
        doc.apply(
            CellsReordered(cell_ids=[ids[9], ids[1], ids[3], ids[5], ids[7]])
        )
        assert _ids(doc) == [ids[9], ids[1], ids[3], ids[5], ids[7]]

        # Create new cells in gaps
        a, b = CellId_t("a"), CellId_t("b")
        doc.apply(CellCreated(id=a, code="new", after=ids[1]))
        doc.apply(CellCreated(id=b, code="new", after=ids[5]))
        assert _ids(doc) == [ids[9], ids[1], a, ids[3], ids[5], b, ids[7]]

        # Verify every cell is findable
        for cid in _ids(doc):
            assert doc[cid].id == cid
