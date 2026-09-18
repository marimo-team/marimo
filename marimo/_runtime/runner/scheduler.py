# Copyright 2026 Marimo. All rights reserved.
"""Per-run cell queue and dependency cancellation."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Protocol

from marimo._runtime import dataflow
from marimo._runtime.runner.hook_context import CancelledCells

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.ids import CellId_t


class Scheduler(Protocol):
    """Cell queue and dependency cancellation."""

    def pending(self) -> bool: ...
    def pop_cell(self) -> CellId_t: ...
    def cancel(self, cell_id: CellId_t) -> None: ...
    def cancelled(self, cell_id: CellId_t) -> bool: ...
    def batch(
        self, cell_ids: Iterable[CellId_t] | None = ...
    ) -> Iterator[Iterable[CellId_t]]: ...
    def requeue(self, cell_ids: Iterable[CellId_t]) -> None: ...
    def requeue_for_rerun(self, cells: set[CellId_t]) -> None: ...


class SequentialScheduler:
    """Single-threaded FIFO queue and dependency cancellation."""

    def __init__(
        self,
        cells_to_run: Sequence[CellId_t],
        graph: DirectedGraph,
    ) -> None:
        self._cells_to_run: deque[CellId_t] = deque(cells_to_run)
        self._cancelled = CancelledCells()
        self._graph = graph

    def pending(self) -> bool:
        return len(self._cells_to_run) > 0

    def pop_cell(self) -> CellId_t:
        return self._cells_to_run.popleft()

    def batch(
        self, cell_ids: Iterable[CellId_t] | None = None
    ) -> Iterator[Iterable[CellId_t]]:
        """Yield single-cell batches from the remaining queue."""
        if cell_ids is not None:
            self.requeue(cell_ids)
        while self._cells_to_run:
            yield (self._cells_to_run.popleft(),)

    def requeue(self, cell_ids: Iterable[CellId_t]) -> None:
        """Replace the pending queue with `cell_ids`."""
        self._cells_to_run.clear()
        self._cells_to_run.extend(cell_ids)

    def requeue_for_rerun(self, cells: set[CellId_t]) -> None:
        """Reschedules by putting `cells` back at the head of the queue.

        Un-cancels each cell and prepends them in **topological order**
        so the next `batch()` yields producers first.
        """
        ordered = dataflow.topological_sort(self._graph, cells)
        # appendleft reverses, so iterate back-to-front to land the
        # topologically-first cell at the head of the queue.
        for cid in reversed(ordered):
            self._cancelled.discard(cid)
            # remove() is a no-op-safe O(n) scan. This also prevents the cell
            # appearing twice in the queue.
            if cid in self._cells_to_run:
                self._cells_to_run.remove(cid)
            self._cells_to_run.appendleft(cid)

    def cancel(self, cell_id: CellId_t) -> None:
        """Mark a cell and its descendants as cancelled."""
        descendants = {
            cid
            for cid in dataflow.transitive_closure(self._graph, {cell_id})
            if cid in self._cells_to_run
        }
        self._cancelled.add(cell_id, descendants)
        for cid in descendants:
            self._graph.cells[cid].set_run_result_status("cancelled")

    def cancelled(self, cell_id: CellId_t) -> bool:
        return cell_id in self._cancelled

    @property
    def cancelled_cells(self) -> CancelledCells:
        return self._cancelled

    @property
    def cells_to_run(self) -> deque[CellId_t]:
        """The live queue. Mutates as cells are popped."""
        return self._cells_to_run
