# Copyright 2025 Marimo. All rights reserved.
"""Parallel cell execution using Python 3.14+ free threading."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Optional

from marimo import _loggers
from marimo._runtime.executor import Executor

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.ids import CellId_t


class CellFutureStub:
    """One stub per cell - coordinates execution order.

    The stub's lock is acquired when registered and released when the cell
    completes. Dependent cells wait on this lock before executing.
    """

    def __init__(self, cell_id: CellId_t, cell_defs: set[str]):
        self.cell_id = cell_id
        self.defs = cell_defs
        self.lock = threading.Lock()
        self._resolved = False
        self._error: Optional[BaseException] = None

    def wait(self) -> None:
        """Block until this cell has completed."""
        with self.lock:
            pass  # Returns when lock released

    def mark_resolved(self) -> None:
        """Mark this stub as resolved."""
        self._resolved = True

    def mark_error(self, error: BaseException) -> None:
        """Mark this stub as failed with an error."""
        self._error = error
        self._resolved = True

    @property
    def resolved(self) -> bool:
        return self._resolved

    @property
    def error(self) -> Optional[BaseException]:
        return self._error


class DeferredResult:
    """Indicates cell execution is deferred to a thread.

    The runner should check for this type and handle accordingly:
    - For cells with output: call wait() to block until complete
    - For cells without output: can continue without waiting
    """

    def __init__(self, future: Future[Any], stub: CellFutureStub):
        self._future = future
        self._stub = stub

    def wait(self) -> Any:
        """Block until cell completes, return result.

        Raises the cell's exception if it failed.
        """
        return self._future.result()

    @property
    def is_ready(self) -> bool:
        """Check if the cell has completed without blocking."""
        return self._future.done()

    @property
    def stub(self) -> CellFutureStub:
        """Get the stub for this deferred result."""
        return self._stub


class ParallelExecutor(Executor):
    """Simple executor that spawns cells to thread pool.

    This executor is naive - it just spawns cells to threads and returns
    a DeferredResult. The runner is responsible for:
    1. Registering stubs for all cells upfront
    2. Detecting DeferredResult and handling appropriately
    3. Waiting for deferred cells at the end

    The thread worker:
    1. Waits on parent cell stubs
    2. Executes via base executor
    3. Releases its own stub
    """

    def __init__(
        self,
        base: Optional[Executor] = None,
        max_workers: Optional[int] = None,
    ) -> None:
        super().__init__(base)
        self.max_workers = max_workers
        self._pool: Optional[ThreadPoolExecutor] = None
        self._stubs: dict[CellId_t, CellFutureStub] = {}

    @property
    def pool(self) -> ThreadPoolExecutor:
        """Lazily create thread pool."""
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._pool

    def register_stub(self, stub: CellFutureStub) -> None:
        """Register a stub for a cell, acquiring its lock.

        Called by the runner before execution begins.
        The lock is held until the cell completes.
        """
        stub.lock.acquire()
        self._stubs[stub.cell_id] = stub

    def clear_stubs(self) -> None:
        """Clear all registered stubs after run completes."""
        self._stubs.clear()

    def execute_cell(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> DeferredResult:
        """Spawn cell to thread pool, return DeferredResult."""
        stub = self._stubs.get(cell.cell_id)
        if stub is None:
            # No stub registered - fall back to synchronous execution
            assert self.base is not None, (
                "ParallelExecutor requires a base executor"
            )
            return self.base.execute_cell(cell, glbls, graph)

        future = self.pool.submit(
            self._run_in_thread, cell, glbls, graph, stub
        )
        return DeferredResult(future, stub)

    async def execute_cell_async(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> DeferredResult:
        """Spawn async cell to thread pool, return DeferredResult."""
        # For now, treat async cells the same as sync cells
        # The thread will call the sync version of base executor
        stub = self._stubs.get(cell.cell_id)
        if stub is None:
            assert self.base is not None, (
                "ParallelExecutor requires a base executor"
            )
            return await self.base.execute_cell_async(cell, glbls, graph)

        future = self.pool.submit(
            self._run_in_thread, cell, glbls, graph, stub
        )
        return DeferredResult(future, stub)

    def _run_in_thread(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
        stub: CellFutureStub,
    ) -> Any:
        """Run a cell in a thread, coordinating via stubs."""
        try:
            # Wait for parent stubs
            parent_ids = graph.parents.get(cell.cell_id, set())
            for parent_id in parent_ids:
                if parent_id in self._stubs:
                    parent_stub = self._stubs[parent_id]
                    parent_stub.wait()
                    # Check if parent failed
                    if parent_stub.error is not None:
                        raise parent_stub.error

            # Execute via base executor
            assert self.base is not None, (
                "ParallelExecutor requires a base executor"
            )
            result = self.base.execute_cell(cell, glbls, graph)

            # Mark as resolved (globals already updated by base executor)
            stub.mark_resolved()
            return result

        except BaseException as e:
            stub.mark_error(e)
            raise

        finally:
            stub.lock.release()

    def shutdown(self) -> None:
        """Shutdown the thread pool."""
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None
