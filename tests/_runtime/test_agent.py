# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import SetCode, Transaction
from marimo._messaging.notebook.document import NotebookCell, NotebookDocument
from marimo._runtime.agent import Agent, AgentReadTracker
from marimo._types.ids import CellId_t


def _cell(
    name: str, *, version: int = 0, code: str | None = None
) -> NotebookCell:
    # Default to non-empty code so the cell counts as stale-eligible; tests
    # that exercise the empty-cell exemption pass code="" explicitly.
    return NotebookCell(
        id=CellId_t(name),
        code=f"# {name}" if code is None else code,
        name="__",
        config=CellConfig(),
        version=version,
    )


def _doc(*cells: NotebookCell) -> NotebookDocument:
    return NotebookDocument(list(cells))


class TestAgentReadTracker:
    def test_record_and_has_read(self) -> None:
        t = AgentReadTracker()
        assert not t.has_read(CellId_t("a"), 0)
        t.record_read(CellId_t("a"), 0)
        assert t.has_read(CellId_t("a"), 0)
        assert not t.has_read(CellId_t("a"), 1)

    def test_record_read_max_merges(self) -> None:
        t = AgentReadTracker()
        t.record_read(CellId_t("a"), 5)
        t.record_read(CellId_t("a"), 2)
        assert t.has_read(CellId_t("a"), 5)
        assert not t.has_read(CellId_t("a"), 6)

    def test_get_stale_cells_never_read(self) -> None:
        t = AgentReadTracker()
        doc = _doc(_cell("a"), _cell("b"))
        assert t.get_stale_cells(doc) == frozenset(
            {CellId_t("a"), CellId_t("b")}
        )

    def test_get_stale_cells_bumped_since_read(self) -> None:
        t = AgentReadTracker()
        doc = _doc(_cell("a", version=0), _cell("b", version=0))
        t.record_read(CellId_t("a"), 0)
        t.record_read(CellId_t("b"), 0)
        assert t.get_stale_cells(doc) == frozenset()

        doc.apply(
            Transaction(
                changes=(SetCode(cell_id=CellId_t("a"), code="x"),),
                source="frontend",
            )
        )
        assert doc.get_cell_version(CellId_t("a")) == 1
        assert t.get_stale_cells(doc) == frozenset({CellId_t("a")})

    def test_get_stale_cells_ignores_deleted(self) -> None:
        t = AgentReadTracker()
        doc = _doc(_cell("a"))
        t.record_read(CellId_t("ghost"), 7)
        assert t.get_stale_cells(doc) == frozenset({CellId_t("a")})

    def test_get_stale_cells_ignores_empty_cells(self) -> None:
        t = AgentReadTracker()
        doc = _doc(
            _cell("empty", code=""),
            _cell("whitespace", code="   \n  "),
            _cell("real", code="a = 1"),
        )
        assert t.get_stale_cells(doc) == frozenset({CellId_t("real")})


class TestAgent:
    def test_default_factory_initializes_tracker(self) -> None:
        a = Agent()
        assert isinstance(a.read_tracker, AgentReadTracker)

    def test_independent_instances(self) -> None:
        a1, a2 = Agent(), Agent()
        a1.read_tracker.record_read(CellId_t("a"), 1)
        assert a1.read_tracker.has_read(CellId_t("a"), 1)
        assert not a2.read_tracker.has_read(CellId_t("a"), 1)
