# Copyright 2026 Marimo. All rights reserved.
"""Scheduler owns the cell queue and cancellation state"""

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
    """Cell queue + cancellation. Surface for future scheduler types."""

    def pending(self) -> bool: ...
    def pop_cell(self) -> CellId_t: ...
    def cancel(self, cell_id: CellId_t) -> None: ...
    def cancelled(self, cell_id: CellId_t) -> bool: ...
    def batch(
        self, cell_ids: Iterable[CellId_t]
    ) -> Iterator[list[CellId_t]]: ...


class SequentialScheduler:
    """Single-threaded FIFO queue + cancellation."""

    def __init__(
        self,
        cells_to_run: Sequence[CellId_t],
        graph: DirectedGraph,
    ) -> None:
        self._cells_to_run: deque[CellId_t] = deque(cells_to_run)
        self._cancelled = CancelledCells()
        self._graph = graph
        self._interrupted = False

    def pending(self) -> bool:
        return not self._interrupted and len(self._cells_to_run) > 0

    def pop_cell(self) -> CellId_t:
        return self._cells_to_run.popleft()

    def batch(self, cell_ids: Iterable[CellId_t]) -> Iterator[list[CellId_t]]:
        """Yield batches of cells to execute.

        Sequential default: one cell per batch.
        """
        self._cells_to_run.clear()
        self._cells_to_run.extend(cell_ids)
        while self._cells_to_run and not self._interrupted:
            yield [self._cells_to_run.popleft()]

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
    def interrupted(self) -> bool:
        return self._interrupted

    @interrupted.setter
    def interrupted(self, value: bool) -> None:
        self._interrupted = value

    @property
    def cancelled_cells(self) -> CancelledCells:
        return self._cancelled

    @property
    def cells_to_run(self) -> deque[CellId_t]:
        """The live queue. Mutates as cells are popped."""
        return self._cells_to_run
