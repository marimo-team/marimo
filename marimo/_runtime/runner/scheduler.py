# Copyright 2026 Marimo. All rights reserved.
"""Scheduler: the per-run cell queue, cancellation, and cell task tracking.

A scheduler drives one run. It holds the queue of cells still to execute,
the set of cancelled cells, and one task for each async cell that is
being evaluated right now.

Active scheduler
----------------
`KernelRuntimeContext._active_scheduler` names the scheduler whose run is
executing right now, and the SIGINT handler reads it to find the run that
it must stop. Several schedulers can be entered on one kernel context at
once, and they nest as a stack. A re-entrant `run_all` suspends the outer
run at its `await`, executes its own cells to completion, and then
restores the outer scheduler. For example, an executing cell can call
`ctx.run_cell` in code mode and enter a nested run. `__aenter__` saves
the scheduler that was active and `__aexit__` restores it, so the field
always names the innermost run. The kernel still serializes top-level
runs. Control requests wait in a queue, and a cascade of state updates
re-enters only after `run_all()` returns.

Cell body marker
----------------
`KernelRuntimeContext._running_cell_body` is a `ContextVar` that holds a
`CellBody`, the scheduler and the cell task whose body the current task
is executing. `cell_body` sets it around the body and resets it after, so
it is `None` in a lifecycle hook, between cells, and in a task that a
hook started. A task started inside the body inherits the value, so the
marker also names the cell that a child task belongs to. A marker whose
cell task is done is stale. It belongs to a task that outlived its cell,
and it is ignored.

SIGINT routing
--------------
The interrupt handler asks the active scheduler what to raise in the
current task, through `interrupt_current_task`, and takes one of four
paths. If the signal arrived in a cell's own task while its body was
executing, `MarimoInterrupt` is raised into the body, as in a sync cell.
If the signal arrived in a child task that the body started, the cell's
task is cancelled at once, which also cancels the other children through
`gather` or a task group, and `CancelledError` is raised into the child.
If a cell task is active but the signal arrived somewhere else, for
example in a lifecycle hook or in a task left over from an earlier cell,
`cancel_all` cancels the cell tasks through the event loop. If no cell
task is active, the signal arrived in a sync cell or between cells, so
`cancel_all` halts the queue and `MarimoInterrupt` is raised.

A future non-blocking `AsyncScheduler.submit()` that returns before
dispatch completes would allow concurrent schedulers on one context. That
change must promote `_active_scheduler` from a saved stack to a plural
`OrderedDict[int, Scheduler]`.
"""

from __future__ import annotations

import asyncio
import weakref
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from marimo._runtime import dataflow
from marimo._runtime.context.types import safe_get_context
from marimo._runtime.control_flow import MarimoInterrupt
from marimo._runtime.runner.hook_context import CancelledCells

if TYPE_CHECKING:
    from collections.abc import (
        AsyncIterator,
        Coroutine,
        Iterable,
        Iterator,
        Sequence,
    )
    from contextlib import AbstractAsyncContextManager, AbstractContextManager
    from typing import Self

    from marimo._runtime.context.kernel_context import KernelRuntimeContext
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._runtime.runner.result import RunResult
    from marimo._types.ids import CellId_t


def _kernel_context() -> KernelRuntimeContext | None:
    """The installed kernel context, or `None` outside a kernel."""
    # Late import to avoid a cycle through the runtime context tree.
    from marimo._runtime.context.kernel_context import KernelRuntimeContext

    ctx = safe_get_context()
    return ctx if isinstance(ctx, KernelRuntimeContext) else None


@dataclass(frozen=True)
class CellBody:
    """The scheduler and cell task whose body a task is executing."""

    scheduler: weakref.ref[Scheduler]
    task: asyncio.Task[Any]


class Scheduler(Protocol):
    """Cell queue + cancellation + async task tracking."""

    interrupted: bool

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
    def owns_task(self, task: asyncio.Task[Any] | None) -> bool: ...
    def cell_body(self) -> AbstractContextManager[None]: ...
    def interrupt_current_task(self) -> type[BaseException] | None: ...
    def cancel_all(self) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc_info: object) -> None: ...


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
        # The scheduler that was active on the context when this one was
        # entered. `__aexit__` restores it, so nested runs on one context
        # form a stack.
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
        """Create the task for `coro` and register it under `cell_id`."""
        if self._interrupted:
            coro.close()
            raise asyncio.CancelledError()
        # A SIGINT between these two statements sets `_interrupted` through
        # `cancel_all` but does not cancel the new task, because it is not
        # registered yet. The check after these statements cancels the task
        # before the loop resumes it. Two adjacent synchronous statements
        # leave the narrowest gap that pure Python allows.
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

    def owns_task(self, task: asyncio.Task[Any] | None) -> bool:
        """Whether `task` is a cell task that this scheduler started."""
        return task is not None and task in self._active.values()

    @contextmanager
    def cell_body(self) -> Iterator[None]:
        """Mark the current task as executing a cell body of this scheduler.

        The marker is a `ContextVar` on the kernel context, so a task that
        starts inside the body inherits it. Without a kernel context nothing
        is recorded, because only the kernel's interrupt handler reads it.
        """
        ctx = _kernel_context()
        if ctx is None:
            yield
            return
        owner = asyncio.current_task()
        assert owner is not None
        # A weak reference, so a long-lived task that a body started does
        # not keep a finished run's graph and task table alive.
        token = ctx._running_cell_body.set(CellBody(weakref.ref(self), owner))
        try:
            yield
        finally:
            ctx._running_cell_body.reset(token)

    def interrupt_current_task(self) -> type[BaseException] | None:
        """Halt this run from the current task and return what to raise there.

        Returns `MarimoInterrupt` when the current task is executing a cell
        body of this run, `CancelledError` when the current task is one that
        such a body started, and `None` when the signal arrived anywhere
        else, including in a task left over from a cell that already ended.
        """
        ctx = _kernel_context()
        task = asyncio.current_task()
        body = ctx._running_cell_body.get() if ctx is not None else None
        if (
            task is None
            or body is None
            or body.scheduler() is not self
            or body.task.done()
        ):
            return None
        self._interrupted = True
        if task is body.task:
            # Raise into the body as in a sync cell. A cancel would take
            # effect only at the body's next `await`, and it would also cut
            # the cell's cleanup short at its first `await`.
            return MarimoInterrupt
        # A `KeyboardInterrupt` that escapes a child task stops the event
        # loop, so the child gets a cancellation. The cell's own task is
        # cancelled as well, because `gather` can return the child's
        # cancellation as a value and a task group ignores it. Cancelling
        # the cell now also cancels its other children through `gather` or
        # the task group.
        body.task.cancel()
        return asyncio.CancelledError

    def cancel_all(self) -> None:
        """Halt the queue and cancel every active cell task."""
        # Set `_interrupted` first, so a SIGINT that arrives between cells,
        # when no task is registered, still halts the queue.
        self._interrupted = True
        for task in list(self._active.values()):
            if task.done():
                continue
            # A plain `task.cancel()` from the signal handler queues the
            # cancel but does not wake the loop from `select()`, so the task
            # keeps sleeping until its next scheduled wakeup.
            task.get_loop().call_soon_threadsafe(task.cancel)

    async def __aenter__(self) -> Self:
        ctx = _kernel_context()
        if ctx is not None:
            # Save the scheduler that is already active and make this one
            # active. A nested run suspends the outer run at its `await`, so
            # SIGINT must reach the innermost scheduler.
            self._prev_scheduler = ctx._active_scheduler
            ctx._active_scheduler = self
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        ctx = _kernel_context()
        if ctx is not None and ctx._active_scheduler is self:
            ctx._active_scheduler = self._prev_scheduler
