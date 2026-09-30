# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import SetCode, Transaction
from marimo._messaging.notebook.document import NotebookCell, NotebookDocument
from marimo._runtime.agent import (
    Agent,
    AgentReadTracker,
    AgentRevisionStore,
)
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


def test_revision_store_is_deduplicated_and_bounded() -> None:
    store = AgentRevisionStore()
    cell_id = CellId_t("cell")

    store.record(cell_id, code="value = 0", name="metric")
    store.record(cell_id, code="value = 0", name="metric")
    for value in range(1, 12):
        store.record(cell_id, code=f"value = {value}", name="metric")

    revisions = store.all()[cell_id]
    assert len(revisions) == 10
    assert revisions[0].code == "value = 2"
    assert revisions[-1].code == "value = 11"
    assert [revision.sequence for revision in revisions] == list(range(3, 13))
    assert store.truncated


def test_revision_store_is_globally_bounded() -> None:
    store = AgentRevisionStore()

    for index in range(101):
        store.record(
            CellId_t(str(index)),
            code=f"value = {index}",
            name="_",
        )

    revisions = store.all()
    assert len(revisions) == 100
    assert CellId_t("0") not in revisions
    assert CellId_t("100") in revisions
    assert store.truncated


def test_revision_store_rejects_source_larger_than_total_budget() -> None:
    store = AgentRevisionStore()

    store.record(
        CellId_t("large"),
        code="x" * (store._MAX_TOTAL_SOURCE_CHARS + 1),
        name="_",
    )

    assert store.all() == {}
    assert store.truncated
