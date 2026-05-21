# Copyright 2026 Marimo. All rights reserved.
"""Scheduler: per-run cell queue, cancellation, and async-task tracking.

Singular-scheduler invariant
----------------------------
At most one `Runner.run_all()` is on the stack per `KernelRuntimeContext`
at any time. The kernel serializes runs — control requests queue and
state-update cascades only re-enter after `run_all()` returns. Embedded
apps push a child `KernelRuntimeContext` (not a nested scheduler on the
same context). Under this invariant, `KernelRuntimeContext._active_scheduler`
can be a singular field.

A future non-blocking `AsyncScheduler.submit()` (returning before
dispatch completes) will break this invariant by allowing concurrent
schedulers on one context; that PR will need to promote
`_active_scheduler` to a plural `OrderedDict[int, Scheduler]`.
`__aenter__` below fails loudly if the invariant is ever silently
broken.
"""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Protocol

from marimo import _loggers
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

    from typing_extensions import Self

    from marimo._runtime.dataflow import DirectedGraph
    from marimo._runtime.runner.result import RunResult
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


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

    def start_task(
        self,
        cell_id: CellId_t,
        coro: Coroutine[Any, Any, RunResult],
    ) -> AsyncIterator[asyncio.Task[RunResult]]: ...
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
            raise asyncio.CancelledError
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
            if ctx._active_scheduler is not None:
                # See module docstring: a second `async with scheduler`
                # on the same context means nested or concurrent runs,
                # which the singular `_active_scheduler` design does not
                # support. Fail loudly so the regression surfaces in
                # tests rather than as a silent SIGINT-routing bug.
                raise RuntimeError(
                    "A scheduler is already active on this context; "
                    "concurrent runs are not supported. This indicates "
                    "either a re-entrant Runner.run_all or a future "
                    "non-blocking scheduler that should be promoting "
                    "_active_scheduler to plural."
                )
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
            ctx._active_scheduler = None
