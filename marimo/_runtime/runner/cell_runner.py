# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import io
import traceback
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from marimo._ast.variables import unmangle_local
from marimo._config.config import ExecutionType, MarimoConfig, OnCellChangeType
from marimo._dependencies.dependencies import DependencyManager
from marimo._dependencies.errors import ManyModulesNotFoundError
from marimo._loggers import marimo_logger
from marimo._messaging.errors import (
    MarimoExceptionRaisedError,
    MarimoSQLError,
    UnknownError,
)
from marimo._messaging.tracebacks import write_traceback
from marimo._runtime import dataflow
from marimo._runtime.context.types import safe_get_context
from marimo._runtime.control_flow import MarimoInterrupt, MarimoStopError
from marimo._runtime.exceptions import (
    MarimoMissingRefError,
    MarimoRuntimeException,
    unwrap_user_exception,
)
from marimo._runtime.executor import (
    EvaluatorConfig,
    ExecutionLifecycle,
    StrictLifecycle,
    build_evaluator,
    resolve_executor,
)
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runner.hook_context import (
    CancelledCells,
    ExceptionOrError,
    ExecutionContextManager,
)
from marimo._runtime.runner.result import RunResult
from marimo._runtime.runner.scheduler import SequentialScheduler
from marimo._sql.error_utils import (
    create_sql_error_from_exception,
    is_sql_parse_error,
)
from marimo._types.ids import CellId_t

LOGGER = marimo_logger()

if TYPE_CHECKING:
    from collections import deque

    from marimo._runtime.runner.hooks import NotebookCellHooks
    from marimo._runtime.state import State


def _should_broadcast_data() -> bool:
    """Whether data (variables, datasets, etc.) should be broadcast.

    Returns True only in edit mode for non-embedded contexts.
    """
    from marimo._runtime.context.kernel_context import KernelRuntimeContext
    from marimo._runtime.context.types import get_context
    from marimo._session.model import SessionMode

    ctx = get_context()
    is_edit_mode = (
        isinstance(ctx, KernelRuntimeContext)
        and ctx.session_mode == SessionMode.EDIT
    )
    # We don't broadcast data in embedded contexts, since the variables
    # panel, etc. should only show the top-level graph's variables.
    return is_edit_mode and not ctx.is_embedded()


def cell_filename(cell_id: CellId_t) -> str:
    """Filename to use when running cells through exec."""
    return f"<cell-{cell_id}>"


__all__ = ["RunResult", "Runner", "cell_filename", "should_show_traceback"]


def should_show_traceback(
    exception: ExceptionOrError | None,
) -> bool:
    if exception is None:
        return True

    # Stop "errors" aren't actually errors but rather a control
    # flow mechanism used by mo.stop() to stop execution; as such
    # a traceback should not be shown for them.
    if isinstance(exception, MarimoStopError):
        return False

    # SQL parsing errors happen in SQL cells so showing a
    # python traceback is not useful.
    return not isinstance(exception, MarimoSQLError)


class Runner:
    """Runner for a collection of cells."""

    def __init__(
        self,
        roots: set[CellId_t],
        graph: dataflow.DirectedGraph,
        glbls: dict[Any, Any],
        debugger: MarimoPdb | None,
        hooks: NotebookCellHooks,
        execution_mode: OnCellChangeType = "autorun",
        execution_type: ExecutionType = "relaxed",
        excluded_cells: set[CellId_t] | None = None,
        execution_context: ExecutionContextManager | None = None,
        user_config: MarimoConfig | None = None,
    ):
        self.graph = graph
        self.debugger = debugger
        self.excluded_cells = excluded_cells or set()
        self.execution_context = execution_context
        self._hooks = hooks
        self.user_config = user_config

        # runtime globals
        self.glbls = glbls
        self.execution_mode: OnCellChangeType = execution_mode
        self.execution_type = execution_type

        # cells that the runner will run, subtracting out cells with errors:
        #
        # cells with errors can't be run, but are still in the graph
        # so that they can be transitioned out of error if a future
        # run request repairs the graph
        self.roots = roots
        cells_to_run_list = Runner.compute_cells_to_run(
            self.graph,
            self.roots,
            self.excluded_cells,
            self.execution_mode,
        )

        # Scheduler owns the queue and cancellation state.
        self._scheduler = SequentialScheduler(cells_to_run_list, self.graph)

        # mapping from cell_id to exception it raised
        self.exceptions: dict[CellId_t, ExceptionOrError] = {}

        # each cell's position in the original run queue (used by
        # resolve_state_updates and _find_first_blocked_missing_ref)
        self._run_position = {
            cell_id: index for index, cell_id in enumerate(cells_to_run_list)
        }

        lifecycles: list[ExecutionLifecycle] = []
        if execution_type == "strict":
            lifecycles.append(StrictLifecycle(self.graph))
        self._evaluator = build_evaluator(
            EvaluatorConfig(executor=resolve_executor(), lifecycles=lifecycles)
        )

    @staticmethod
    def compute_cells_to_run(
        graph: dataflow.DirectedGraph,
        roots: set[CellId_t],
        excluded_cells: set[CellId_t],
        execution_mode: OnCellChangeType,
    ) -> list[CellId_t]:
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

        if execution_mode == "autorun":
            # in autorun/eager mode, descendants are also run;
            cells_to_run = dataflow.transitive_closure(
                graph,
                cells_to_run,
                relatives=dataflow.get_import_block_relatives(graph),
            )

        sorted_cells = dataflow.topological_sort(
            graph,
            cells_to_run - excluded_cells,
        )

        # Overridden cells may be on the path of a UI element update.
        if (
            (ctx := safe_get_context()) is not None
            and ctx.is_embedded()
            and ((overrides := ctx.app.overrides()) is not None)
        ):
            sorted_cells = dataflow.prune_cells_for_overrides(
                graph, sorted_cells, overrides
            )

        return sorted_cells

    @property
    def cells_to_run(self) -> deque[CellId_t]:
        return self._scheduler.cells_to_run

    @property
    def cancelled_cells(self) -> CancelledCells:
        return self._scheduler.cancelled_cells

    @property
    def interrupted(self) -> bool:
        return self._scheduler.interrupted

    @interrupted.setter
    def interrupted(self, value: bool) -> None:
        self._scheduler.interrupted = value

    def cancel(self, cell_id: CellId_t) -> None:
        """Mark a cell (and its descendants) as cancelled."""
        self._scheduler.cancel(cell_id)

    def cancelled(self, cell_id: CellId_t) -> bool:
        """Return whether a cell has been cancelled."""
        return self._scheduler.cancelled(cell_id)

    def pending(self) -> bool:
        """Whether there are more cells to run."""
        return self._scheduler.pending()

    def _get_run_position(self, cell_id: CellId_t) -> int | None:
        """Position in the original run queue"""
        return self._run_position.get(cell_id, None)

    def _runs_after(self, source: CellId_t, target: CellId_t) -> bool | None:
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
                        break  # cell already matched; skip remaining refs
        return cids_to_run

    def pop_cell(self) -> CellId_t:
        """Get the next cell to run."""
        return self._scheduler.pop_cell()

    def _run_result_from_exception(
        self,
        output: Any,
        unwrapped_exception: BaseException | None,
        cell_id: CellId_t,
    ) -> tuple[RunResult, BaseException | None]:
        exception: ExceptionOrError | None = unwrapped_exception
        if isinstance(exception, MarimoMissingRefError):
            ref, blamed_cell = self._get_blamed_cell(exception)
            # All MarimoMissingRefErrors should be caused caused by
            # NameErrors if they are the cause of MarimoRuntimeExceptions.
            if exception.name_error is not None:
                unwrapped_exception = exception.name_error
            # Provide output context for said missing reference errors.
            if self.execution_type == "strict":
                output = MarimoExceptionRaisedError(
                    f"marimo came across the undefined variable `{ref}` "
                    "during runtime. This is possible in strict mode when "
                    "static analysis is unable to properly resolve the "
                    "reference due  to direct access (e.g. "
                    "`globals()['var']`) or circuitous definitions (e.g.  "
                    "by reassigning variables to different functions). If "
                    "this failure is not the result of either of these "
                    "cases, please consider reporting this issue to "
                    "https://github.com/marimo-team/marimo/issues. "
                    "Definition expected in cell : ",
                    "NameError",
                    blamed_cell,
                )
                exception = output
            elif blamed_cell != cell_id:
                possibly_deleted = any(
                    ref in cell.deleted_refs
                    for cell in self.graph.cells.values()
                )

                deleted_message = (
                    " Another cell may have deleted it with the del operator."
                    if possibly_deleted
                    else ""
                )
                output = MarimoExceptionRaisedError(
                    f"Name `{ref}` is not defined.{deleted_message} "
                    "It was expected to be defined in ",
                    "NameError",
                    blamed_cell,
                )
                exception = output
            else:
                # Default to regular error for self reference in relaxed
                # mode.
                exception = unwrapped_exception
        # Handle other special runtime errors.
        elif isinstance(
            unwrapped_exception,
            (ModuleNotFoundError, ManyModulesNotFoundError),
        ):
            self.missing_packages = True

            # If the user has a library and a file with the same name
            # we should inform that this is a conflict.
            if isinstance(unwrapped_exception, ModuleNotFoundError):
                try:
                    module_name = getattr(unwrapped_exception, "name", "")
                    # Grab the base module name if it's a submodule
                    module_name = module_name.split(".")[0]

                    if Path(
                        f"{module_name}.py"
                    ).exists() and DependencyManager.has(module_name):
                        error_message = f"There is a file named '{module_name}.py' which conflicts with the imported package. Please rename the file."
                        output = MarimoExceptionRaisedError(
                            error_message,
                            unwrapped_exception.__class__.__name__,
                            None,
                        )
                        LOGGER.error(error_message)
                        exception = output
                except Exception:
                    pass
        # Handle SQL parsing errors
        elif unwrapped_exception is not None and is_sql_parse_error(
            unwrapped_exception
        ):
            cell = self.graph.cells[cell_id]
            output = create_sql_error_from_exception(unwrapped_exception, cell)
            exception = output
        elif isinstance(unwrapped_exception, MarimoStopError):
            output = unwrapped_exception.output
            exception = unwrapped_exception
        return RunResult(
            output=output, exception=exception
        ), unwrapped_exception

    async def run(self, cell_id: CellId_t) -> RunResult:
        """Run a cell."""
        if self.debugger is not None:
            last_tb = self.debugger._last_tracebacks.pop(cell_id, None)
            if last_tb == self.debugger._last_traceback:
                self.debugger._last_traceback = None

        cell = self.graph.cells[cell_id]
        # The Evaluator captures all body/lifecycle exceptions into the
        # returned RunResult; cell_id-specific classification + side
        # effects are applied below in `_finalize_run_result`.
        try:
            raw_result = await self._evaluator.evaluate_interruptible(
                cell, self.glbls
            )
            run_result = self._finalize_run_result(raw_result, cell_id)
        except BaseException:
            # Defensive: an unexpected escape from the Evaluator or a bug
            # in `_finalize_run_result` would otherwise tear down the
            # runner loop. Degrade gracefully with an empty RunResult.
            LOGGER.error(
                """marimo encountered an internal error.

                marimo finished executing a cell, but did not produce
                a run result.

                Please copy this message and paste it in a GitHub issue:

                https://github.com/marimo-team/marimo/issues

                Any additional context of what caused this error, such
                as sample code to reproduce, will help us debug.
                """
            )
            run_result = RunResult(output=None, exception=None)

        # Mark as interrupted if the cell raised a MarimoInterrupt
        # Set here since failed async can also trigger an Interrupt.
        if isinstance(run_result.exception, MarimoInterrupt):
            self.interrupted = True

        self._update_debugger_state(run_result, cell_id)

        if run_result.exception is not None:
            self.exceptions[cell_id] = run_result.exception

        return run_result

    def _finalize_run_result(
        self, raw_result: RunResult, cell_id: CellId_t
    ) -> RunResult:
        """Classify the Evaluator's RunResult and apply Runner side effects."""
        exc = raw_result.exception
        if exc is None:
            return raw_result
        if not isinstance(exc, BaseException):
            # A non-``BaseException`` Error shape (e.g. the
            # ``MarimoStrictExecutionError`` produced by
            # ``StrictLifecycle.setup`` via ``Skip(result=...)``).
            # Cancel descendants and surface the payload as-is.
            self.cancel(cell_id)
            return raw_result

        if isinstance(exc, asyncio.exceptions.CancelledError):
            # User interrupt — async cells can only be cancelled via SIGINT.
            # Surface as MarimoInterrupt so `run` flips `self.interrupted`.
            tmpio = io.StringIO()
            traceback.print_exception(
                type(exc), exc, exc.__traceback__, file=tmpio
            )
            tmpio.seek(0)
            write_traceback(tmpio.read())
            return RunResult(output=None, exception=MarimoInterrupt())

        # Should cover all cell runtime exceptions.
        if isinstance(exc, MarimoRuntimeException):
            # Unwrap the user exception and upgrade a raw NameError to
            # MarimoMissingRefError when the missing name is defined
            # elsewhere in the graph.
            unwrapped_exception = unwrap_user_exception(exc, self.graph)

            # Interrupts are sometimes sent multiple times; in particular,
            # it appears that polars forwards interrupts, so interrupting
            # pl.read_parquet() causes two interrupts to be sent instead of one
            # on macOS. This try/except is here to catch that extra
            # interrupt.
            #
            # TODO(akshayka): Find a less brittle way of handling interrupts.
            try:
                run_result, unwrapped_exception = (
                    self._run_result_from_exception(
                        None, unwrapped_exception, cell_id
                    )
                )
            except KeyboardInterrupt:
                run_result = RunResult(
                    output=None, exception=MarimoInterrupt()
                )

            # Exceptions trigger cancellation of descendants.
            #
            # TODO(akshayka): A SIGINT during cancel() can interrupt this
            # call, so this should be lifted to a non-interruptible path.
            self.cancel(cell_id)

            if should_show_traceback(run_result.exception):
                tmpio = io.StringIO()
                # The executors explicitly raise cell exceptions from base
                # exceptions such that the stack trace is cleaner.
                # Verbosity is for Python < 3.10 compat
                # See https://docs.python.org/3/library/traceback.html
                exception_type = (
                    type(unwrapped_exception) if unwrapped_exception else None
                )
                maybe_traceback = (
                    unwrapped_exception.__traceback__
                    if unwrapped_exception
                    else None
                )
                traceback.print_exception(
                    exception_type,
                    unwrapped_exception,
                    maybe_traceback,
                    file=tmpio,
                )
                tmpio.seek(0)
                write_traceback(tmpio.read())
            return run_result

        # Anything else escaping the Evaluator is unexpected.
        LOGGER.error(f"Unexpected error type: {exc}")
        self.cancel(cell_id)
        tmpio = io.StringIO()
        traceback.print_exception(
            type(exc), exc, exc.__traceback__, file=tmpio
        )
        tmpio.seek(0)
        write_traceback(tmpio.read())
        return RunResult(output=None, exception=UnknownError(f"{exc}"))

    def _update_debugger_state(
        self, run_result: RunResult, cell_id: CellId_t
    ) -> None:
        """Skip marimo frames in the debugger and stash the cell's traceback."""
        # if a debugger is active, force it to skip past marimo code.
        try:
            # Bdb defines the botframe attribute and sets it to non-None
            # when it starts up
            if self.debugger is not None:
                if (
                    hasattr(self.debugger, "botframe")
                    and self.debugger.botframe is not None
                ):
                    self.debugger.set_continue()
                # Hold on to this information for debugging postmortem etc.
                if run_result.exception is not None and hasattr(
                    run_result.exception, "__traceback__"
                ):
                    tb = run_result.exception.__traceback__
                    if isinstance(tb, TracebackType):
                        self.debugger._last_traceback = tb
                        self.debugger._last_tracebacks[cell_id] = tb
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

    def _get_blamed_cell(
        self, e: MarimoMissingRefError
    ) -> tuple[str, CellId_t | None]:
        ref = e.ref
        blamed_cell = None
        try:
            (blamed_cell, *_) = self.graph.get_defining_cells(ref)
        except (KeyError, ValueError):
            # The reference is not found anywhere else in the graph
            # but it might be private
            ref, var_cell_id = unmangle_local(ref)
            if var_cell_id:
                blamed_cell = var_cell_id
        return ref, blamed_cell

    def _find_first_blocked_missing_ref(
        self, cell_id: CellId_t
    ) -> CellId_t | None:
        """Return the first out-of-run ancestor still in a stopped/errored state."""
        cell = self.graph.cells[cell_id]
        for ref in cell.refs:
            if ref in self.glbls:
                # The reference is already available
                continue
            for defining_cell_id in self.graph.get_defining_cells(ref):
                if defining_cell_id in self._run_position:
                    # The defining cell is part of this run
                    continue
                defining_cell = self.graph.cells[defining_cell_id]
                if defining_cell.run_result_status == "exception":
                    return defining_cell_id
        return None

    async def run_all(self) -> None:
        from marimo._runtime.runner.hook_context import (
            OnFinishHookContext,
            PostExecutionHookContext,
            PreExecutionHookContext,
            PreparationHookContext,
        )

        prep_ctx = PreparationHookContext(
            graph=self.graph,
            execution_mode=self.execution_mode,
            cells_to_run=self.cells_to_run,
        )
        LOGGER.debug("Running preparation hooks")
        for prep_hook in self._hooks.preparation_hooks:
            prep_hook(prep_ctx)

        pre_exec_ctx = PreExecutionHookContext(
            graph=self.graph,
            execution_mode=self.execution_mode,
        )
        all_temporaries: frozenset[str] = (
            frozenset().union(
                *(cell.temporaries for cell in self.graph.cells.values())
            )
            if self.graph.cells
            else frozenset()
        )
        post_exec_ctx = PostExecutionHookContext(
            graph=self.graph,
            glbls=self.glbls,
            execution_context=self.execution_context,
            exceptions=self.exceptions,
            cancelled_cells=self.cancelled_cells,
            all_temporaries=all_temporaries,
            should_broadcast_data=_should_broadcast_data(),
            user_config=self.user_config,
        )

        while self.pending():
            cell_id = self.pop_cell()
            LOGGER.debug("Cell runner processing %s", cell_id)
            cell = self.graph.cells[cell_id]

            blocked_ancestor_id = self._find_first_blocked_missing_ref(cell_id)
            if blocked_ancestor_id is not None:
                # Cancel cell_id and descendants before the check below.
                LOGGER.debug(
                    "%s cancelled: ancestor %s still stopped",
                    cell_id,
                    blocked_ancestor_id,
                )
                if blocked_ancestor_id not in self.exceptions:
                    # TODO (jlehuen): We wouldn't have to create this MarimoStopError if those were stored directly
                    # in CellImpl.exception. See: marimo._runtime.runner.hooks_post_execution._set_run_result_status
                    self.exceptions[blocked_ancestor_id] = self.graph.cells[
                        blocked_ancestor_id
                    ].exception or MarimoStopError(None)
                pending = {cell_id} | {
                    cid
                    for cid in dataflow.transitive_closure(
                        self.graph, {cell_id}, inclusive=False
                    )
                    if cid in self.cells_to_run
                }
                for cid in pending:
                    self.graph.cells[cid].set_run_result_status("cancelled")
                self.cancelled_cells.add(blocked_ancestor_id, pending)

            # Update run result status for cells that won't run.
            #
            # Hack: frontend sets status to queued on run, so we also have to
            # set runtime_state to get FE to transition.
            if self.cancelled(cell_id):
                LOGGER.debug("%s cancelled", cell_id)
                cell.set_run_result_status("cancelled")
                cell.set_runtime_state("idle")
                continue
            if cell.config.disabled:
                LOGGER.debug("%s disabled", cell_id)
                cell.set_run_result_status("disabled")
                cell.set_runtime_state("idle")
                continue
            if self.graph.is_disabled(cell_id):
                LOGGER.debug("%s disabled transitively", cell_id)
                cell.set_run_result_status("disabled")
                cell.set_runtime_state("disabled-transitively")
                continue

            LOGGER.debug("Running pre_execution hooks")
            for pre_hook in self._hooks.pre_execution_hooks:
                pre_hook(cell, pre_exec_ctx)
            LOGGER.debug("Running cell %s", cell_id)
            if self.execution_context is not None:
                try:
                    # TODO(akshayka): The execution context should be pushed
                    # down to as close to kernel execution as possible.
                    with self.execution_context(cell_id) as exc_ctx:
                        run_result = await self.run(cell_id)
                        run_result.accumulated_output = exc_ctx.output
                        LOGGER.debug("Running post_execution hooks in context")
                        for post_hook in self._hooks.post_execution_hooks:
                            post_hook(cell, post_exec_ctx, run_result)
                except KeyboardInterrupt:
                    LOGGER.error(
                        """
                        A keyboard interrupt was raised but not handled by the runner.
                        """
                    )

            else:
                run_result = await self.run(cell_id)
                LOGGER.debug("Running post_execution hooks out of context")
                for post_hook in self._hooks.post_execution_hooks:
                    post_hook(cell, post_exec_ctx, run_result)

        finish_ctx = OnFinishHookContext(
            graph=self.graph,
            cells_to_run=self.cells_to_run,
            interrupted=self.interrupted,
            cancelled_cells=self.cancelled_cells,
            exceptions=self.exceptions,
        )
        LOGGER.debug("Running on_finish hooks")
        for finish_hook in self._hooks.on_finish_hooks:
            finish_hook(finish_ctx)
