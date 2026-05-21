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
