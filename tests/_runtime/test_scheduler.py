# Copyright 2026 Marimo. All rights reserved.
"""Queue + cancellation invariants for SequentialScheduler."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from marimo._runtime.runner.scheduler import SequentialScheduler
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    import pytest


def _empty_graph() -> MagicMock:
    """A graph whose transitive_closure returns just the input cell."""
    g = MagicMock()
    g.cells = {}
    return g


def test_pending_and_pop_cell_fifo() -> None:
    cells = [CellId_t("a"), CellId_t("b"), CellId_t("c")]
    sched = SequentialScheduler(cells, graph=_empty_graph())

    assert sched.pending() is True
    assert sched.pop_cell() == "a"
    assert sched.pop_cell() == "b"
    assert sched.pop_cell() == "c"
    assert sched.pending() is False


def test_interrupted_blocks_pending() -> None:
    sched = SequentialScheduler([CellId_t("a")], graph=_empty_graph())

    assert sched.pending() is True
    sched.interrupted = True
    assert sched.pending() is False


def test_cancel_marks_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock graph: transitive_closure returns just the cell itself, no
    # descendants. Cell registered in graph.cells so set_run_result_status
    # has a target.
    g = MagicMock()
    cid = CellId_t("a")
    cell_mock = MagicMock()
    g.cells = {cid: cell_mock}

    def fake_closure(graph: object, roots: set[CellId_t]) -> set[CellId_t]:
        del graph
        return set(roots)

    monkeypatch.setattr(
        "marimo._runtime.dataflow.transitive_closure", fake_closure
    )
    sched = SequentialScheduler([cid], graph=g)
    assert sched.cancelled(cid) is False
    sched.cancel(cid)
    assert sched.cancelled(cid) is True
    cell_mock.set_run_result_status.assert_called_with("cancelled")


def test_requeue_for_rerun_moves_producer_ahead_of_queued_consumer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A producer already queued *behind* the consumer is moved to the head
    so it runs before the consumer's retry — not left stranded behind it
    (which would re-trip on the stale value forever)."""
    p, c, y = CellId_t("P"), CellId_t("C"), CellId_t("Y")

    def fake_topo(graph: object, cells: set[CellId_t]) -> list[CellId_t]:
        del graph
        return [cid for cid in (p, c) if cid in cells]  # producer first

    monkeypatch.setattr("marimo._runtime.dataflow.topological_sort", fake_topo)
    # Consumer C is the current (popped) cell, not in the queue; producer P
    # is already queued, behind Y.
    sched = SequentialScheduler([y, p], graph=_empty_graph())
    sched.requeue_for_rerun({p, c})
    assert list(sched.cells_to_run) == [p, c, y]


def test_requeue_for_rerun_no_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A requeued cell already in the queue is moved, not duplicated."""
    p, c = CellId_t("P"), CellId_t("C")

    def fake_topo(graph: object, cells: set[CellId_t]) -> list[CellId_t]:
        del graph
        return [cid for cid in (p, c) if cid in cells]

    monkeypatch.setattr("marimo._runtime.dataflow.topological_sort", fake_topo)
    sched = SequentialScheduler([c], graph=_empty_graph())
    sched.requeue_for_rerun({p, c})
    queued = list(sched.cells_to_run)
    assert queued == [p, c]
    assert queued.count(c) == 1


def test_requeue_for_rerun_uncancels_stranded_descendants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requeuing a raiser (without its descendants in the rerun set, as
    `cells_to_rerun = self | producers` does) must not leave the descendants
    it previously cancelled stuck in the cancelled set."""
    r, d = CellId_t("R"), CellId_t("D")
    g = MagicMock()
    g.cells = {r: MagicMock(), d: MagicMock()}

    def fake_closure(graph: object, roots: set[CellId_t]) -> set[CellId_t]:
        del graph, roots
        return {r, d}  # cancelling R also cancels descendant D

    def fake_topo(graph: object, cells: set[CellId_t]) -> list[CellId_t]:
        del graph
        return [cid for cid in (r, d) if cid in cells]

    monkeypatch.setattr(
        "marimo._runtime.dataflow.transitive_closure", fake_closure
    )
    monkeypatch.setattr("marimo._runtime.dataflow.topological_sort", fake_topo)

    sched = SequentialScheduler([r, d], graph=g)
    sched.cancel(r)
    assert sched.cancelled(r) is True
    assert sched.cancelled(d) is True

    # Rerun set contains only the raiser, not descendant D.
    sched.requeue_for_rerun({r})
    assert sched.cancelled(r) is False
    assert sched.cancelled(d) is False


def test_batch_yields_singletons() -> None:
    sched = SequentialScheduler([], graph=_empty_graph())
    cells = [CellId_t("a"), CellId_t("b"), CellId_t("c")]
    # batch() yields iterables, not indexable lists — callers iterate with
    # ``for cell_id in batch:`` rather than ``batch[0]``.
    batches = [list(b) for b in sched.batch(cells)]
    assert batches == [["a"], ["b"], ["c"]]


def test_batch_respects_interrupt() -> None:
    sched = SequentialScheduler([], graph=_empty_graph())
    cells = [CellId_t("a"), CellId_t("b"), CellId_t("c")]
    iterator = sched.batch(cells)
    assert list(next(iterator)) == ["a"]
    sched.interrupted = True
    # Generator stops once interrupted is set.
    remaining = list(iterator)
    assert remaining == []
