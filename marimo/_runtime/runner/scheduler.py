# Copyright 2026 Marimo. All rights reserved.
"""Scheduler: per-run cell queue, cancellation, and async-task tracking.

Active-scheduler stack
----------------------
`KernelRuntimeContext._active_scheduler` points at the scheduler whose
run is currently executing, so the SIGINT handler can route a cancel to
it. Runs nest as a stack on a single context: a re-entrant `run_all`
(e.g. code_mode `ctx.run_cell` driving a run from inside a running cell)
suspends the outer run at its `await`, runs to completion, then restores
the outer scheduler. `__aenter__` saves the previously-active scheduler
and `__aexit__` restores it, so the field always names the innermost
(currently executing) run. The kernel still serializes top-level runs —
control requests queue and state-update cascades only re-enter after
`run_all()` returns.

A future non-blocking `AsyncScheduler.submit()` (returning before
dispatch completes) would allow genuinely *concurrent* schedulers on one
context; that PR will need to promote `_active_scheduler` from a saved
stack to a plural `OrderedDict[int, Scheduler]`.
"""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Protocol

from marimo._runtime import dataflow
from marimo._runtime.context.types import safe_get_context
from marimo._runtime.runner.hook_context import CancelledCells

if TYPE_CHECKING:
    from collections.abc import (
        AsyncIterator,
        Coroutine,
        Iterable,
        Iterator,
        Sequence,
    )
    from contextlib import AbstractAsyncContextManager

    from typing_extensions import Self

    from marimo._runtime.dataflow import DirectedGraph
    from marimo._runtime.runner.result import RunResult
    from marimo._types.ids import CellId_t


class Scheduler(Protocol):
    """Cell queue + cancellation + async task tracking."""

    def pending(self) -> bool: ...
    def pop_cell(self) -> CellId_t: ...
    def cancel(self, cell_id: CellId_t) -> None: ...
    def cancelled(self, cell_id: CellId_t) -> bool: ...
    def batch(
        self, cell_ids: Iterable[CellId_t] | None = ...
    ) -> Iterator[Iterable[CellId_t]]: ...
    def requeue(self, cell_ids: Iterable[CellId_t]) -> None: ...
    def requeue_for_rerun(self, cells: set[CellId_t]) -> None: ...

    def start_task(
        self,
        cell_id: CellId_t,
        coro: Coroutine[Any, Any, RunResult],
    ) -> AbstractAsyncContextManager[asyncio.Task[RunResult]]: ...
    def has_active_tasks(self) -> bool: ...
    def cancel_all(self) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc_info: Any) -> None: ...


class SequentialScheduler:
    """Single-threaded FIFO queue + cancellation + async task tracking."""

    def __init__(
        self,
        cells_to_run: Sequence[CellId_t],
        graph: DirectedGraph,
    ) -> None:
        self._cells_to_run: deque[CellId_t] = deque(cells_to_run)
        self._cancelled = CancelledCells()
        self._graph = graph
        self._interrupted = False
        self._active: dict[CellId_t, asyncio.Task[Any]] = {}
        # Scheduler that was active on the context when this one was
        # entered. Saved on `__aenter__`, restored on `__aexit__`, so
        # nested `run_all` calls on the same context compose as a stack
        # (see module docstring).
        self._prev_scheduler: Scheduler | None = None

    def pending(self) -> bool:
        return not self._interrupted and len(self._cells_to_run) > 0

    def pop_cell(self) -> CellId_t:
        return self._cells_to_run.popleft()

    def batch(
        self, cell_ids: Iterable[CellId_t] | None = None
    ) -> Iterator[Iterable[CellId_t]]:
        """Yield batches of cells to execute (1-tuple per batch here).

        If `cell_ids` is given, the queue is replaced first — kept for
        callers that drive the scheduler without going through
        `requeue` (and for tests). When `None`, consume the existing
        `_cells_to_run` as-is.
        """
        if cell_ids is not None:
            self.requeue(cell_ids)
        while self._cells_to_run and not self._interrupted:
            yield (self._cells_to_run.popleft(),)

    def requeue(self, cell_ids: Iterable[CellId_t]) -> None:
        """Replace the pending queue with `cell_ids`."""
        self._cells_to_run.clear()
        self._cells_to_run.extend(cell_ids)

    def requeue_for_rerun(self, cells: set[CellId_t]) -> None:
        """Soft-cancel: put `cells` back at the head of the queue.

        Called when a lifecycle raises
        `MarimoCancelCellError(cells_to_rerun=...)` — e.g. `CachedLifecycle`
        signaling that producers need their bodies to actually run.
        Un-cancels each cell and prepends them in **topological order**
        (producers before consumers) so the next `batch()` yields the
        producers first; they emit real values before the consumer that
        tripped retries. Without the topo order a consumer requeued ahead
        of its producer would re-trip on the same stale value and loop
        forever (the cells set has no inherent ordering).
        """
        ordered = dataflow.topological_sort(self._graph, cells)
        # appendleft reverses, so iterate back-to-front to land the
        # topologically-first cell at the head of the queue.
        for cid in reversed(ordered):
            self._cancelled.discard(cid)
            # Move to the head even when already queued: a cell left at a
            # later position than its producer would re-trip on the stale
            # value. A deque has no move op, so drop the stale position
            # (remove() is a no-op-safe O(n) scan) before prepending — this
            # also prevents the cell appearing twice in the queue.
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

    @asynccontextmanager
    async def start_task(
        self,
        cell_id: CellId_t,
        coro: Coroutine[Any, Any, RunResult],
    ) -> AsyncIterator[asyncio.Task[RunResult]]:
        """Atomically create and register a task for `coro`.

        Closes the SIGINT race where a task is created before being
        tracked: `ensure_future` and `_register_task` run as two
        adjacent synchronous statements (the narrowest gap in pure
        Python), then `_interrupted` is re-checked. A SIGINT delivered
        between them flips `_interrupted` via `cancel_all`; the
        re-check cancels the freshly-registered task before the loop
        ever resumes it.
        """
        if self._interrupted:
            coro.close()
            raise asyncio.CancelledError()
        task = asyncio.ensure_future(coro)
        self._register_task(cell_id, task)
        if self._interrupted:
            task.cancel()
        try:
            yield task
        finally:
            self._unregister_task(cell_id)

    def _register_task(
        self, cell_id: CellId_t, task: asyncio.Task[Any]
    ) -> None:
        self._active[cell_id] = task

    def _unregister_task(self, cell_id: CellId_t) -> None:
        self._active.pop(cell_id, None)

    def has_active_tasks(self) -> bool:
        return any(not t.done() for t in self._active.values())

    def cancel_all(self) -> None:
        # Set `_interrupted` first so a SIGINT arriving between cells
        # (no task registered) still halts the queue.
        #
        # `call_soon_threadsafe` is required: a plain `task.cancel()`
        # from the signal-handler thread queues the cancel but doesn't
        # wake the loop's `select()` — the task keeps sleeping until
        # its next scheduled wakeup.
        self._interrupted = True
        for task in list(self._active.values()):
            if task.done():
                continue
            task.get_loop().call_soon_threadsafe(task.cancel)

    async def __aenter__(self) -> Self:
        # Late import to avoid a cycle through the runtime context tree.
        from marimo._runtime.context.kernel_context import (
            KernelRuntimeContext,
        )

        ctx = safe_get_context()
        if isinstance(ctx, KernelRuntimeContext):
            # Save any scheduler already active on the context and make
            # this one active. A re-entrant `run_all` on the same context
            # (e.g. code_mode `ctx.run_cell` driving a run from inside a
            # running cell) suspends the outer run at its `await`, runs to
            # completion here, then restores the outer scheduler on exit —
            # a clean stack. SIGINT routes to the innermost (currently
            # executing) scheduler, which is the correct target.
            self._prev_scheduler = ctx._active_scheduler
            ctx._active_scheduler = self
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        from marimo._runtime.context.kernel_context import (
            KernelRuntimeContext,
        )

        ctx = safe_get_context()
        if (
            isinstance(ctx, KernelRuntimeContext)
            and ctx._active_scheduler is self
        ):
            ctx._active_scheduler = self._prev_scheduler
