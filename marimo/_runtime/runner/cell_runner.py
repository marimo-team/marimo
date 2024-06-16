# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import functools
import io
import signal
import threading
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterator, Optional, Union

from marimo._ast.cell import (
    CellId_t,
    CellImpl,
)
from marimo._config.config import ExecutionType, OnCellChangeType
from marimo._loggers import marimo_logger
from marimo._messaging.errors import Error, MarimoStrictExecutionError
from marimo._messaging.tracebacks import write_traceback
from marimo._runtime import dataflow
from marimo._runtime.control_flow import (
    MarimoInterrupt,
    MarimoStopError,
)
from marimo._runtime.executor import (
    MarimoMissingRefError,
    execute_cell,
    execute_cell_async,
)
from marimo._runtime.marimo_pdb import MarimoPdb

LOGGER = marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._runtime.context.types import ExecutionContext
    from marimo._runtime.state import State


def cell_filename(cell_id: CellId_t) -> str:
    """Filename to use when running cells through exec."""
    return f"<cell-{cell_id}>"


ErrorObjects = Union[BaseException, Error]


@dataclass
class RunResult:
    # Raw output of cell: last expression
    output: Any
    # Exception raised by cell, if any
    exception: Optional[ErrorObjects]
    # Accumulated output: via imperative mo.output.append()
    accumulated_output: Any = None

    def success(self) -> bool:
        """Whether the cell expected successfully"""
        return self.exception is None


class Runner:
    """Runner for a collection of cells."""

    def __init__(
        self,
        roots: set[CellId_t],
        graph: dataflow.DirectedGraph,
        glbls: dict[Any, Any],
        debugger: MarimoPdb | None,
        execution_mode: OnCellChangeType = "autorun",
        execution_type: ExecutionType = "relaxed",
        excluded_cells: set[CellId_t] | None = None,
        execution_context: Callable[
            [CellId_t], contextlib._GeneratorContextManager[ExecutionContext]
        ]
        | None = None,
        preparation_hooks: Sequence[Callable[["Runner"], Any]] | None = None,
        pre_execution_hooks: Sequence[Callable[[CellImpl, "Runner"], Any]]
        | None = None,
        post_execution_hooks: Sequence[
            Callable[[CellImpl, "Runner", RunResult], Any]
        ]
        | None = None,
        on_finish_hooks: Sequence[Callable[["Runner"], Any]] | None = None,
    ):
        self.graph = graph
        self.debugger = debugger
        self.excluded_cells = excluded_cells or set()

        # injected context and hooks
        self.execution_context = execution_context
        self.preparation_hooks: Sequence[Callable[["Runner"], Any]] = (
            preparation_hooks or []
        )
        self.pre_execution_hooks: Sequence[
            Callable[[CellImpl, "Runner"], Any]
        ] = pre_execution_hooks or []
        self.post_execution_hooks: Sequence[
            Callable[[CellImpl, "Runner", RunResult], Any]
        ] = post_execution_hooks or []
        self.on_finish_hooks: Sequence[Callable[["Runner"], Any]] = (
            on_finish_hooks or []
        )

        # runtime globals
        self.glbls = glbls
        self.execution_mode = execution_mode
        self.execution_type = execution_type

        # cells that the runner will run, subtracting out cells with errors:
        #
        # cells with errors can't be run, but are still in the graph
        # so that they can be transitioned out of error if a future
        # run request repairs the graph
        self.cells_to_run: list[CellId_t]

        # Runner always runs stale ancestors, if any.
        cells_to_run = roots.union(
            dataflow.transitive_closure(
                graph,
                roots,
                children=False,
                inclusive=False,
                predicate=lambda cell: cell.stale,
            )
        )
        if self.execution_mode == "autorun":
            # in autorun/eager mode, descendants are also run
            cells_to_run = dataflow.transitive_closure(graph, cells_to_run)
        self.cells_to_run = dataflow.topological_sort(
            graph,
            cells_to_run - self.excluded_cells,
        )

        # map from a cell that was cancelled to its descendants that have
        # not yet run:
        self.cells_cancelled: dict[CellId_t, set[CellId_t]] = {}
        # whether the runner has been interrupted
        self.interrupted = False
        # mapping from cell_id to exception it raised
        self.exceptions: dict[CellId_t, ErrorObjects] = {}

        # each cell's position in the run queue
        self._run_position = {
            cell_id: index for index, cell_id in enumerate(self.cells_to_run)
        }

    # Adapted from
    # https://github.com/ipython/ipykernel/blob/eddd3e666a82ebec287168b0da7cfa03639a3772/ipykernel/ipkernel.py#L312  # noqa: E501
    @staticmethod
    @contextlib.contextmanager
    def _cancel_on_sigint(future: asyncio.Future[Any]) -> Iterator[None]:
        """ContextManager for capturing SIGINT and cancelling a future

        SIGINT raises in the event loop when running async code,
        but we want it to halt a coroutine.

        Ideally, it would raise KeyboardInterrupt, but this turns it into a
        CancelledError.
        """
        sigint_future: asyncio.Future[int] = asyncio.Future()

        # whichever future finishes first,
        # cancel the other one
        def cancel_unless_done(f: asyncio.Future[Any], _: Any) -> None:
            if f.cancelled() or f.done():
                return
            f.cancel()

        # when sigint finishes,
        # abort the coroutine with CancelledError
        sigint_future.add_done_callback(
            functools.partial(cancel_unless_done, future)
        )
        # when the main future finishes,
        # stop watching for SIGINT events
        future.add_done_callback(
            functools.partial(cancel_unless_done, sigint_future)
        )

        def handle_sigint(*_: Any) -> None:
            if sigint_future.cancelled() or sigint_future.done():
                return
            # mark as done, to trigger cancellation
            sigint_future.set_result(1)

        # set the custom sigint handler during this context
        save_sigint = signal.signal(signal.SIGINT, handle_sigint)
        try:
            yield
        finally:
            # restore the previous sigint handler
            signal.signal(signal.SIGINT, save_sigint)

    def cancel(self, cell_id: CellId_t) -> None:
        """Mark a cell (and its descendants) as cancelled."""
        self.cells_cancelled[cell_id] = set(
            cid
            for cid in dataflow.transitive_closure(self.graph, set([cell_id]))
            if cid in self.cells_to_run
        )

    def cancelled(self, cell_id: CellId_t) -> bool:
        """Return whether a cell has been cancelled."""
        return any(
            cell_id in cancelled for cancelled in self.cells_cancelled.values()
        )

    def pending(self) -> bool:
        """Whether there are more cells to run."""
        return not self.interrupted and len(self.cells_to_run) > 0

    def _get_run_position(self, cell_id: CellId_t) -> Optional[int]:
        """Position in the original run queue"""
        return (
            self._run_position[cell_id]
            if cell_id in self._run_position
            else None
        )

    def _runs_after(
        self, source: CellId_t, target: CellId_t
    ) -> Optional[bool]:
        """Compare run positions.

        Returns `True` if source runs after target, `False` if target runs
        after source, or `None` if not comparable
        """
        source_pos = self._get_run_position(source)
        target_pos = self._get_run_position(target)
        if source_pos is None or target_pos is None:
            return None
        return source_pos > target_pos

    def resolve_state_updates(
        self,
        state_updates: dict[State[Any], CellId_t],
    ) -> set[CellId_t]:
        """
        Get cells that need to be run as a consequence of state updates

        A cell is marked as needing to run if all of the following are true:

            1. The runner was not interrupted.
            2. It was not already run after its setter was called.
            3. It isn't the cell that called the setter (unless the state
               object was configured to allow self loops).
            4. It is not errored (unable to run) or cancelled.
            5. It has among its refs the state object whose setter
               was invoked.

        (3) means that a state update in a given cell will never re-trigger
        the same cell to run. This is similar to how interacting with
        a UI element in the cell that created it won't re-trigger the cell,
        and this behavior is useful when tying UI elements together with a
        state object.

        **Arguments.**

        - state_updates: mapping from state object to the cell that last ran
          its setter
        - errored_cells: cell ids that are unable to run
        """
        # No updates when the runner is interrupted (condition 1)
        if self.interrupted:
            return set()

        cids_to_run: set[CellId_t] = set()
        for state, setter_cell_id in state_updates.items():
            for cid, cell in self.graph.cells.items():
                # Don't re-run cells that already ran with new state (2)
                if self._runs_after(source=cid, target=setter_cell_id):
                    continue
                # No self-loops (3)
                if cid == setter_cell_id and not state.allow_self_loops:
                    continue
                # No errorred/cancelled cells (4)
                if cid in self.excluded_cells or self.cancelled(cid):
                    continue
                # State object in refs (5)
                for ref in cell.refs:
                    # run this cell if any of its refs match the state object
                    # by object ID (via is operator)
                    if ref in self.glbls and self.glbls[ref] is state:
                        cids_to_run.add(cid)
        return cids_to_run

    def pop_cell(self) -> CellId_t:
        """Get the next cell to run."""
        return self.cells_to_run.pop(0)

    async def run(self, cell_id: CellId_t) -> RunResult:
        """Run a cell."""

        cell = self.graph.cells[cell_id]
        try:
            if cell.is_coroutine():
                return_value_future = asyncio.ensure_future(
                    execute_cell_async(
                        cell,
                        self.glbls,
                        self.graph,
                        execution_type=self.execution_type,
                    )
                )
                if threading.current_thread() == threading.main_thread():
                    # edit mode: need to handle user interrupts
                    with Runner._cancel_on_sigint(return_value_future):
                        return_value = await return_value_future
                else:
                    # run mode: can't use signal.signal, not interruptible
                    # by user anyway.
                    return_value = await return_value_future
            else:
                return_value = execute_cell(
                    cell,
                    self.glbls,
                    self.graph,
                    execution_type=self.execution_type,
                )
            run_result = RunResult(output=return_value, exception=None)
        except (MarimoInterrupt, asyncio.exceptions.CancelledError) as e:
            # User interrupt
            # interrupt the entire runner
            if isinstance(e, asyncio.exceptions.CancelledError):
                # Async cells can only be cancelled via a user interrupt
                e = MarimoInterrupt()
            self.interrupted = True
            run_result = RunResult(output=None, exception=e)
            tmpio = io.StringIO()
            traceback.print_exc(file=tmpio)
            tmpio.seek(0)
            write_traceback(tmpio.read())
        except MarimoStopError as e:
            # Raised by mo.stop().
            # cancel only the descendants of this cell
            self.cancel(cell_id)
            run_result = RunResult(output=e.output, exception=e)
            # don't print a traceback, since quitting is the intended
            # behavior (like sys.exit())
        except MarimoMissingRefError as e:
            # In strict mode, marimo refuses to evaluate a cell if there are
            # missing definitions. Since the cell hasn't run, this is a pre
            # check error, but still mark descendants as cancelled.
            self.cancel(cell_id)
            try:
                (blamed_cell, *_) = self.graph.get_defining_cells(e.ref)
            except KeyError:
                # This should never happen, but just in case
                blamed_cell = e.ref

            output = MarimoStrictExecutionError(
                f"marimo was unable to resolve "
                f"a reference to `{e.ref}` in cell : ",
                e.ref,
                blamed_cell,
            )
            run_result = RunResult(output=output, exception=output)
        except BaseException as e:
            # Catch-all: some libraries have bugs and raise BaseExceptions,
            # which shouldn't crash the marimo kernel
            if isinstance(e, ModuleNotFoundError):
                self.missing_packages = True

            self.cancel(cell_id)
            run_result = RunResult(output=None, exception=e)
            tmpio = io.StringIO()
            traceback.print_exc(file=tmpio)
            tmpio.seek(0)
            write_traceback(tmpio.read())
        finally:
            # if a debugger is active, force it to skip past marimo code.
            try:
                # Bdb defines the botframe attribute and sets it to non-None
                # when it starts up
                if (
                    self.debugger is not None
                    and hasattr(self.debugger, "botframe")
                    and self.debugger.botframe is not None
                ):
                    self.debugger.set_continue()
            except Exception as debugger_error:
                # This has never been hit, but just in case -- don't want
                # to crash the kernel.
                LOGGER.error(
                    """Internal marimo error. Please copy this message and
                    paste it in a GitHub issue:

                    https://github.com/marimo-team/marimo/issues

                    An exception raised attempting to continue debugger (%s).
                    """,
                    str(debugger_error),
                )

        if run_result.exception is not None:
            self.exceptions[cell_id] = run_result.exception

        return run_result

    async def run_all(self) -> None:
        for prep_hook in self.preparation_hooks:
            prep_hook(self)

        while self.pending():
            cell_id = self.pop_cell()
            if self.cancelled(cell_id):
                continue
            if self.graph.is_disabled(cell_id):
                continue
            cell = self.graph.cells[cell_id]
            for pre_hook in self.pre_execution_hooks:
                pre_hook(cell, self)
            if self.execution_context is not None:
                with self.execution_context(cell_id) as exc_ctx:
                    run_result = await self.run(cell_id)
                    run_result.accumulated_output = exc_ctx.output
            else:
                run_result = await self.run(cell_id)
            for post_hook in self.post_execution_hooks:
                post_hook(cell, self, run_result)

        for finish_hook in self.on_finish_hooks:
            finish_hook(self)
