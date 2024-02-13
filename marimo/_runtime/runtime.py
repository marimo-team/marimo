# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import builtins
import contextlib
import dataclasses
import functools
import io
import itertools
import multiprocessing as mp
import os
import signal
import sys
import threading
import time
import traceback
from collections.abc import Iterable, Sequence
from typing import Any, Callable, Iterator, Optional

from marimo import _loggers
from marimo._ast.cell import CellConfig, CellId_t
from marimo._ast.compiler import compile_cell
from marimo._ast.visitor import Name, is_local
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.errors import (
    Error,
    MarimoAncestorStoppedError,
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
    MarimoSyntaxError,
    UnknownError,
)
from marimo._messaging.ops import (
    CellOp,
    CompletedRun,
    FunctionCallResult,
    HumanReadableStatus,
    Interrupted,
    RemoveUIElements,
    VariableDeclaration,
    Variables,
    VariableValue,
    VariableValues,
)
from marimo._messaging.streams import (
    ThreadSafeStderr,
    ThreadSafeStdin,
    ThreadSafeStdout,
    ThreadSafeStream,
)
from marimo._messaging.types import (
    KernelMessage,
    Stderr,
    Stdin,
    Stdout,
    Stream,
)
from marimo._output import formatting
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import MarimoConvertValueException
from marimo._runtime import cell_runner, dataflow, marimo_pdb
from marimo._runtime.complete import complete
from marimo._runtime.context import (
    ContextNotInitializedError,
    get_context,
    get_global_context,
    initialize_context,
)
from marimo._runtime.control_flow import MarimoInterrupt, MarimoStopError
from marimo._runtime.input_override import input_override
from marimo._runtime.redirect_streams import redirect_streams
from marimo._runtime.requests import (
    AppMetadata,
    CompletionRequest,
    ControlRequest,
    CreationRequest,
    DeleteRequest,
    ExecuteMultipleRequest,
    ExecutionRequest,
    FunctionCallRequest,
    SetCellConfigRequest,
    SetUIElementValueRequest,
    StopRequest,
)
from marimo._runtime.state import State
from marimo._runtime.validate_graph import check_for_errors
from marimo._server.types import QueueType
from marimo._utils.signals import restore_signals
from marimo._utils.typed_connection import TypedConnection

LOGGER = _loggers.marimo_logger()


@mddoc
def defs() -> tuple[str, ...]:
    """Get the definitions of the currently executing cell.

    **Returns**:

    - tuple of the currently executing cell's defs.
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return tuple()

    if ctx.kernel.execution_context is not None:
        return tuple(
            sorted(
                defn
                for defn in ctx.kernel.graph.cells[
                    ctx.kernel.execution_context.cell_id
                ].defs
            )
        )
    return tuple()


@mddoc
def refs() -> tuple[str, ...]:
    """Get the references of the currently executing cell.

    **Returns**:

    - tuple of the currently executing cell's refs.
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return tuple()

    # builtins that have not been shadowed by the user
    unshadowed_builtins = set(builtins.__dict__.keys()).difference(
        set(ctx.kernel.graph.definitions.keys())
    )

    if ctx.kernel.execution_context is not None:
        return tuple(
            sorted(
                defn
                for defn in ctx.kernel.graph.cells[
                    ctx.kernel.execution_context.cell_id
                ].refs
                # exclude builtins that have not been shadowed
                if defn not in unshadowed_builtins
            )
        )
    return tuple()


@dataclasses.dataclass
class ExecutionContext:
    cell_id: CellId_t
    setting_element_value: bool
    # output object set imperatively
    output: Optional[list[Html]] = None


@dataclasses.dataclass
class CellMetadata:
    """CellMetadata

    Metadata the kernel needs to persist, even when a cell is removed
    from the graph or when a cell can't be formed from user code due to syntax
    errors.
    """

    config: CellConfig = dataclasses.field(default_factory=CellConfig)


class Kernel:
    """Kernel that manages the dependency graph and its execution.

    Args:

    - cell_configs: initial configuration for each cell
    - input_override: a function that overrides the builtin input() function
    """

    def patch_pdb(self, debugger: marimo_pdb.MarimoPdb) -> None:
        import pdb

        # Patch Pdb so manually instantiated debuggers create our debugger
        pdb.Pdb = marimo_pdb.MarimoPdb  # type: ignore[misc, assignment]
        pdb.set_trace = functools.partial(
            marimo_pdb.set_trace, debugger=debugger
        )

    def __init__(
        self,
        cell_configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        stream: Stream,
        stdout: Stdout | None,
        stderr: Stderr | None,
        stdin: Stdin | None,
        input_override: Callable[[Any], str] = input_override,
    ) -> None:
        self.app_metadata = app_metadata
        self.stream = stream
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = stdin
        self.debugger = marimo_pdb.MarimoPdb(
            stdout=self.stdout, stdin=self.stdin
        )
        self.patch_pdb(self.debugger)

        self.globals: dict[Any, Any] = {
            "__name__": "__main__",
            "__builtins__": globals()["__builtins__"],
            "input": input_override,
            "__file__": self.app_metadata.filename,
        }
        self.graph = dataflow.DirectedGraph()
        self.cell_metadata: dict[CellId_t, CellMetadata] = {
            cell_id: CellMetadata(config=config)
            for cell_id, config in cell_configs.items()
        }

        self.execution_context: Optional[ExecutionContext] = None
        # initializers to override construction of ui elements
        self.ui_initializers: dict[str, Any] = {}
        # errored cells
        self.errors: dict[CellId_t, tuple[Error, ...]] = {}
        # Mapping from state to the cell when its setter
        # was invoked. New state updates evict older ones.
        self.state_updates: dict[State[Any], CellId_t] = {}

        # an empty string represents the current directory
        exec("import sys; sys.path.append('')", self.globals)
        exec("import marimo as __marimo__", self.globals)

    def start_completion_worker(
        self, completion_queue: QueueType[CompletionRequest]
    ) -> None:
        """Must be called after context is initialized"""
        threading.Thread(
            target=complete,
            args=(completion_queue, self.graph, get_context().stream),
            daemon=True,
        ).start()

    @contextlib.contextmanager
    def _install_execution_context(
        self, cell_id: CellId_t, setting_element_value: bool = False
    ) -> Iterator[ExecutionContext]:
        self.execution_context = ExecutionContext(
            cell_id, setting_element_value
        )
        with get_context().provide_ui_ids(str(cell_id)), redirect_streams(
            cell_id,
            stream=self.stream,
            stdout=self.stdout,
            stderr=self.stderr,
            stdin=self.stdin,
        ):
            try:
                yield self.execution_context
            finally:
                self.execution_context = None

    def _try_registering_cell(
        self, cell_id: CellId_t, code: str
    ) -> Optional[Error]:
        """Attempt to register a cell with given id and code.

        Precondition: a cell with the supplied id must not already exist in the
        graph.

        If cell was unable to be registered, returns an Error object.
        """
        error: Optional[Error] = None
        try:
            cell = compile_cell(code, cell_id=cell_id)
        except Exception as e:
            cell = None
            if isinstance(e, SyntaxError):
                tmpio = io.StringIO()
                traceback.print_exc(file=tmpio, limit=0)
                tmpio.seek(0)
                syntax_error = tmpio.read().split("\n")
                # first line has the form File XXX, line XXX
                syntax_error[0] = syntax_error[0][
                    syntax_error[0].find("line") :
                ]
                error = MarimoSyntaxError(msg="\n".join(syntax_error))
            else:
                tmpio = io.StringIO()
                traceback.print_exc(file=tmpio)
                tmpio.seek(0)
                error = UnknownError(msg=tmpio.read())

        if cell_id in self.cell_metadata and cell is not None:
            # If we already have a config for this cell id, restore it
            # This can happen when a cell was previously deactivated (due to a
            # syntax error or multiple definition error, for example) and then
            # re-registered
            cell.configure(self.cell_metadata[cell_id].config)
        elif cell_id not in self.cell_metadata:
            self.cell_metadata[cell_id] = CellMetadata()

        if cell is not None:
            self.graph.register_cell(cell_id, cell)
            LOGGER.debug("registered cell %s", cell_id)
            LOGGER.debug("parents: %s", self.graph.parents[cell_id])
            LOGGER.debug("children: %s", self.graph.children[cell_id])

        return error

    def _maybe_register_cell(
        self, cell_id: CellId_t, code: str
    ) -> tuple[set[CellId_t], Optional[Error]]:
        """Register a cell (given by id, code) if not already registered.

        If a cell with id `cell_id` is already registered but with different
        code, that cell is deleted from the graph and a new cell with the
        same id but different code is registered.

        Returns:
        - a set of ids for cells that were previously children of `cell_id`;
          only non-empty when `cell-id` was already registered but with
          different code.
        - an `Error` if the cell couldn't be registered, `None` otherwise
        """
        previous_children = set()
        error = None
        if not self.graph.is_cell_cached(cell_id, code):
            if cell_id in self.graph.cells:
                LOGGER.debug("Deleting cell %s", cell_id)
                previous_children = self._deactivate_cell(cell_id)
            error = self._try_registering_cell(cell_id, code)

        LOGGER.debug(
            "graph:\n\tcell id %s\n\tparents %s\n\tchildren %s\n\tsiblings %s",
            cell_id,
            self.graph.parents,
            self.graph.children,
            self.graph.siblings,
        )
        return previous_children, error

    def _delete_names(
        self, names: Iterable[Name], exclude_defs: set[Name]
    ) -> None:
        """Delete `names` from kernel, except for `exclude_defs`"""
        for name in names:
            if name in exclude_defs:
                continue

            if name in self.globals:
                del self.globals[name]

            if (
                "__annotations__" in self.globals
                and name in self.globals["__annotations__"]
            ):
                del self.globals["__annotations__"][name]

    def _invalidate_cell_state(
        self,
        cell_id: CellId_t,
        exclude_defs: Optional[set[Name]] = None,
        deletion: bool = False,
    ) -> None:
        """Cleanup state associated with this cell.

        Deletes a cell's defs from the kernel state, except for the names in
        `exclude_defs`, and instructs the frontend to invalidate its UI
        elements.
        """
        defs_to_delete = self.graph.cells[cell_id].defs
        self._delete_names(
            defs_to_delete, exclude_defs if exclude_defs is not None else set()
        )
        get_context().cell_lifecycle_registry.dispose(
            cell_id, deletion=deletion
        )
        RemoveUIElements(cell_id=cell_id).broadcast()

    def _deactivate_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Deactivate: remove from graph, invalidate state, but keep metadata

        Keeps the cell's config, in case we see the same cell again.

        In contrast to deleting a cell, which fully scrubs the cell
        from the kernel and graph.
        """
        if cell_id not in self.errors:
            self._invalidate_cell_state(cell_id, deletion=True)
            return self.graph.delete_cell(cell_id)
        else:
            # An errored cell can be thought of as a cell that's in the graph
            # but that has no state in the kernel (because it was never run).
            # Its defs may overlap with defs of a non-errored cell, so we MUST
            # NOT delete/cleanup its defs from the kernel (i.e., an errored
            # cell shouldn't invalidate state of another cell).
            self.graph.delete_cell(cell_id)
            return set()

    def _delete_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Delete a cell from the kernel and the graph.

        Deletion from the kernel involves removing cell's defs and
        de-registering its UI Elements.

        Deletion from graph is forwarded to graph object.
        """
        del self.cell_metadata[cell_id]
        return self._deactivate_cell(cell_id)

    def mutate_graph(
        self,
        execution_requests: Sequence[ExecutionRequest],
        deletion_requests: Sequence[DeleteRequest],
    ) -> set[CellId_t]:
        """Add and remove cells to/from the graph.

        This method adds the cells in `execution_requests` to the kernel's
        graph (deleting old versions of these cells, if any), and removes the
        cells in `deletion_requests` from the kernel's graph.

        The mutations that this method makes to the graph renders the
        kernel inconsistent (stale).

        This method does not register errors for cells that were previously
        valid and are not descendants of any of the newly registered cells.
        This is important for multiple definition errors, since a user may
        absent-mindedly redefine an existing name when creating a new cell:
        such a mistake shouldn't invalidate the program state.

        Returns
        - set of cells that must be run to return kernel to consistent state
        """
        LOGGER.debug("Current set of errors: %s", self.errors)
        cells_before_mutation = set(self.graph.cells.keys())
        cells_with_errors_before_mutation = set(self.errors.keys())

        # The set of cells that were successfully registered
        registered_cell_ids = set()

        # The set of cells that need to be re-run due to cells being
        # deleted/re-registered.
        cells_that_were_children_of_mutated_cells = set()

        # Cells that were unable to be added to the graph due to syntax errors
        syntax_errors: dict[CellId_t, Error] = {}

        # Register and delete cells
        for er in execution_requests:
            old_children, error = self._maybe_register_cell(
                er.cell_id, er.code
            )
            cells_that_were_children_of_mutated_cells |= old_children
            if error is None:
                registered_cell_ids.add(er.cell_id)
            else:
                syntax_errors[er.cell_id] = error

        for dr in deletion_requests:
            cells_that_were_children_of_mutated_cells |= self._delete_cell(
                dr.cell_id
            )
        cells_in_graph = set(self.graph.cells.keys())

        # Check for semantic errors, like multiple definition errors, cycle
        # errors, and delete nonlocal errors.
        semantic_errors = check_for_errors(self.graph)
        LOGGER.debug("After mutation, syntax errors %s", syntax_errors)
        LOGGER.debug("Semantic errors %s", semantic_errors)

        # Prune semantic errors: we won't invalidate cells that were previously
        # valid, except for cells we just tried to register
        #
        # We don't want "action at a distance": running
        # a cell shouldn't invalidate cells that were previously valid
        # and weren't requested for execution
        previously_valid_cell_ids = (
            cells_in_graph
            # cells successfully registered
            - registered_cell_ids
            # cells that already had errors
            - cells_with_errors_before_mutation
        )

        # defs that we shouldn't remove from the graph
        keep_alive_defs: set[Name] = set()
        for cid in list(semantic_errors.keys()):
            # If a cell was previously valid, don't invalidate it unless
            # we have to, ie, unless it is a descendant of a just-registered
            # cell that has an error
            #
            # Handles the introduction of a multiple definition error, eg
            #
            # cell 1: x = 0
            # cell 2 (requested for execution): x = 1
            #
            # cell 1 won't be invalidated because cell 1 was previously valid
            # and there's no path from cell 2 to cell 1
            if cid in previously_valid_cell_ids and not any(
                self.graph.get_path(other_cid, cid)
                for other_cid in registered_cell_ids
            ):
                del semantic_errors[cid]
                keep_alive_defs |= self.graph.cells[cid].defs

        all_errors = {**semantic_errors}
        for cid, error in syntax_errors.items():
            # No chance of collision because cells with syntax errors are not
            # in the graph, so can't be in semantic errors
            assert cid not in all_errors
            all_errors[cid] = (error,)

        LOGGER.debug(
            "Final set of errors, after pruning valid cells: %s", all_errors
        )
        cells_with_errors_after_mutation = set(all_errors.keys())

        # Construct sets of cells that will need to be re-run.

        # Cells that previously had errors (eg, multiple definition or cycle)
        # that no longer have errors need to be refreshed.
        cells_that_no_longer_have_errors = (
            cells_with_errors_before_mutation
            - cells_with_errors_after_mutation
        ) & cells_in_graph
        for cid in cells_that_no_longer_have_errors:
            # clear error outputs before running
            CellOp.broadcast_output(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="",
                cell_id=cid,
                status=None,
            )

        # Cells that were successfully registered need to be run
        cells_registered_without_error = (
            registered_cell_ids - cells_with_errors_after_mutation
        )

        # Cells that didn't have errors associated with them before the
        # run request but now have errors; these cells' descendants
        # will need to be run. Handles the case where a cell was cached (cell's
        # code didn't change), so its previous children were not added to
        # cells_that_were_children_of_mutated_cells
        cells_transitioned_to_error = (
            cells_with_errors_after_mutation
            - cells_with_errors_before_mutation
        ) & cells_before_mutation

        # Invalidate state defined by error-ed cells, with the exception of
        # names that were defined by valid cells (relevant for multiple
        # definition errors)
        for cid in all_errors:
            if cid not in self.graph.cells:
                # error is a registration error
                continue
            self._invalidate_cell_state(cid, exclude_defs=keep_alive_defs)

        roots = (
            set(
                itertools.chain(
                    cells_registered_without_error,
                    cells_that_were_children_of_mutated_cells,
                    cells_transitioned_to_error,
                    cells_that_no_longer_have_errors,
                )
            )
            & cells_in_graph
        )
        descendants = (
            dataflow.transitive_closure(self.graph, roots)
            # cells with errors can't be run, but are still in the graph
            # so that they can be transitioned out of error if a future
            # run request repairs the graph
            - cells_with_errors_after_mutation
        )

        self.errors = all_errors
        for cid in self.errors:
            if (
                # Cells with syntax errors are not in the graph
                cid in self.graph.cells
                and not self.graph.cells[cid].config.disabled
                and self.graph.is_disabled(cid)
            ):
                # this may be the first time we're seeing the cell: set its
                # status
                self.graph.cells[cid].set_status("disabled-transitively")
            CellOp.broadcast_error(
                data=self.errors[cid],
                clear_console=True,
                cell_id=cid,
                status=None,
            )

        Variables(
            variables=[
                VariableDeclaration(
                    name=variable,
                    declared_by=list(declared_by),
                    used_by=list(self.graph.get_referring_cells(variable)),
                )
                for variable, declared_by in self.graph.definitions.items()
            ]
        ).broadcast()
        return descendants

    def _run_cells(self, cell_ids: set[CellId_t]) -> None:
        """Run cells and any state updates they trigger"""

        while cells_with_stale_state := self._run_cells_internal(cell_ids):
            LOGGER.debug("Running state updates ...")
            cell_ids = dataflow.transitive_closure(
                self.graph, cells_with_stale_state
            )
        LOGGER.debug("Finished run.")

    def _run_cells_internal(self, cell_ids: set[CellId_t]) -> set[CellId_t]:
        """Run cells, send outputs to frontends

        Returns set of cells that need to be re-run due to state updates.
        """
        LOGGER.debug("preparing to evaluate cells %s", cell_ids)

        # Status updates: cells transition to queued, except for
        # cells that are disabled (explicitly or implicitly).
        for cid in cell_ids:
            if self.graph.is_disabled(cid):
                self.graph.cells[cid].set_status(status="stale")
            else:
                self.graph.cells[cid].set_status(status="queued")
        runner = cell_runner.Runner(
            cell_ids=cell_ids,
            graph=self.graph,
            glbls=self.globals,
            debugger=self.debugger,
        )

        # I/O
        #
        # TODO(akshayka): ignore stdin (always read empty string)
        # TODO(akshayka): redirect input to frontend (override builtins.input)
        #                 or ignore/disallow input, since most users will use a
        #                 marimo UI component anyway
        # TODO(akshayka): when no logger is configured, log output is not
        #                 redirected to frontend (it's printed to console),
        #                 which is incorrect
        # TODO(akshayka): pdb support
        LOGGER.debug("final set of cells to run %s", runner.cells_to_run)
        while runner.pending():
            cell_id = runner.pop_cell()
            if runner.cancelled(cell_id):
                continue
            # State clean-up: don't leak names, UI elements, ...
            self._invalidate_cell_state(cell_id)
            cell = self.graph.cells[cell_id]
            if cell.stale:
                continue

            LOGGER.debug("running cell %s", cell_id)
            cell.set_status(status="running")

            with self._install_execution_context(cell_id) as exc_ctx:
                run_result = runner.run(cell_id)
                # Don't rebroadcast an output that was already sent
                #
                # 1. if run_result.output is not None, need to send it
                # 2. otherwise if exc_ctx.output is None, then need to send
                #    the (empty) output (to clear it)
                new_output = (
                    run_result.output is not None or exc_ctx.output is None
                )

            values = [
                VariableValue(
                    name=variable,
                    value=(
                        self.globals[variable]
                        if variable in self.globals
                        else None
                    ),
                )
                for variable in self.graph.cells[cell_id].defs
            ]

            if values:
                VariableValues(variables=values).broadcast()

            cell.set_status(status="idle")
            if (
                run_result.success()
                or isinstance(run_result.exception, MarimoStopError)
            ) and new_output:
                with self._install_execution_context(cell_id) as exc_ctx:
                    formatted_output = formatting.try_format(run_result.output)
                if formatted_output.traceback is not None:
                    with self._install_execution_context(cell_id):
                        sys.stderr.write(formatted_output.traceback)
                CellOp.broadcast_output(
                    channel=CellChannel.OUTPUT,
                    mimetype=formatted_output.mimetype,
                    data=formatted_output.data,
                    cell_id=cell_id,
                    status=cell.status,
                )
            elif isinstance(run_result.exception, MarimoInterrupt):
                LOGGER.debug("Cell %s was interrupted", cell_id)
                # don't clear console because this cell was running and
                # its console outputs are not stale
                CellOp.broadcast_error(
                    data=[MarimoInterruptionError()],
                    clear_console=False,
                    cell_id=cell_id,
                    status=cell.status,
                )
            elif run_result.exception is not None:
                LOGGER.debug(
                    "Cell %s raised %s",
                    cell_id,
                    type(run_result.exception).__name__,
                )
                # don't clear console because this cell was running and
                # its console outputs are not stale
                exception_type = type(run_result.exception).__name__
                CellOp.broadcast_error(
                    data=[
                        MarimoExceptionRaisedError(
                            msg="This cell raised an exception: %s%s"
                            % (
                                exception_type,
                                (
                                    f"('{str(run_result.exception)}')"
                                    if str(run_result.exception)
                                    else ""
                                ),
                            ),
                            exception_type=exception_type,
                            raising_cell=None,
                        )
                    ],
                    clear_console=False,
                    cell_id=cell_id,
                    status=cell.status,
                )

            if get_global_context().mpl_installed:
                # ensures that every cell gets a fresh axis.
                exec("__marimo__._output.mpl.close_figures()", self.globals)

        if runner.cells_to_run:
            assert runner.interrupted
            for cid in runner.cells_to_run:
                # `cid` was not run. Its defs should be deleted.
                self.graph.cells[cid].set_status("idle")
                self._invalidate_cell_state(cid)
                CellOp.broadcast_error(
                    data=[MarimoInterruptionError()],
                    # these cells are transitioning from queued to stopped
                    # (interrupted); they didn't get to run, so their consoles
                    # reflect a previous run and should be cleared
                    clear_console=True,
                    cell_id=cid,
                    status="idle",
                )

        for raising_cell in runner.cells_cancelled:
            for cid in runner.cells_cancelled[raising_cell]:
                # `cid` was not run. Its defs should be deleted.
                self.graph.cells[cid].set_status("idle")
                self._invalidate_cell_state(cid)
                exception = runner.exceptions[raising_cell]
                data: Error
                if isinstance(exception, MarimoStopError):
                    data = MarimoAncestorStoppedError(
                        msg=(
                            "This cell wasn't run because an "
                            "ancestor was stopped with `mo.stop`: "
                        ),
                        raising_cell=raising_cell,
                    )
                else:
                    exception_type = type(
                        runner.exceptions[raising_cell]
                    ).__name__
                    data = MarimoExceptionRaisedError(
                        msg=(
                            "An ancestor raised an exception "
                            f"({exception_type}): "
                        ),
                        exception_type=exception_type,
                        raising_cell=raising_cell,
                    )
                CellOp.broadcast_error(
                    data=[data],
                    # these cells are transitioning from queued to stopped
                    # (interrupted); they didn't get to run, so their consoles
                    # reflect a previous run and should be cleared
                    clear_console=True,
                    cell_id=cid,
                    status="idle",
                )

        cells_with_stale_state = runner.resolve_state_updates(
            self.state_updates, self.errors
        )
        self.state_updates.clear()
        return cells_with_stale_state

    def register_state_update(self, state: State[Any]) -> None:
        """Register a state object as having been updated.

        Should be called when a state's setter is called.
        """
        # store the state and the currently executing cell
        assert self.execution_context is not None
        self.state_updates[state] = self.execution_context.cell_id
        # TODO(akshayka): Send VariableValues message for any globals
        # bound to this state object (just like UI elements)

    def delete(self, request: DeleteRequest) -> None:
        """Delete a cell from kernel and graph."""
        cell_id = request.cell_id
        if cell_id in self.graph.cells:
            self._run_cells(
                self.mutate_graph(
                    execution_requests=[], deletion_requests=[request]
                )
            )

    def run(self, execution_requests: Sequence[ExecutionRequest]) -> None:
        """Run cells and their descendants.

        The cells may be cells already existing in the graph or new cells.
        Adds the cells in `execution_requests` to the graph before running
        them.
        """

        self._run_cells(
            self.mutate_graph(execution_requests, deletion_requests=[])
        )

    def set_cell_config(self, request: SetCellConfigRequest) -> None:
        """Update cell configs.

        Cells that are enabled (via config) but stale are run as a side-effect.
        """
        # TODO: state transitions to disabled-transitively, stale, idle should
        # be handled by the graph, not by kernel ...
        # Stale cells that are enabled will need to be run.
        cells_to_run: set[CellId_t] = set()
        for cell_id, config in request.configs.items():
            # store the config, regardless of whether we've seen the cell yet
            self.cell_metadata[cell_id] = CellMetadata(
                config=CellConfig.from_dict(config)
            )
            cell = self.graph.cells.get(cell_id)
            if cell is None:
                continue
            cell.configure(config)
            if not cell.config.disabled:
                cells_to_run = self.graph.enable_cell(cell_id)
            elif cell.config.disabled:
                self.graph.disable_cell(cell_id)

        if cells_to_run:
            self._run_cells(
                dataflow.transitive_closure(self.graph, cells_to_run)
            )

    def set_ui_element_value(self, request: SetUIElementValueRequest) -> None:
        """Set the value of a UI element bound to a global variable.

        Runs cells that reference the UI element by name.
        """
        # Resolve lenses on request, if any: any element that is a view
        # of another parent element is resolved to its parent. In particular,
        # interacting with a view triggers reactive execution through the
        # source (parent).
        resolved_requests: dict[str, Any] = {}
        ui_element_registry = get_context().ui_element_registry
        for object_id, value in request.ids_and_values:
            try:
                resolved_id, resolved_value = ui_element_registry.resolve_lens(
                    object_id, value
                )
            except (KeyError, RuntimeError):
                # KeyError: Trying to access an unnamed UIElement
                # RuntimeError: UIElement was deleted somehow
                LOGGER.debug(
                    "Could not resolve UIElement with id%s", object_id
                )
                continue
            resolved_requests[resolved_id] = resolved_value
        del request

        referring_cells = set()
        for object_id, value in resolved_requests.items():
            try:
                component = ui_element_registry.get_object(object_id)
                LOGGER.debug(
                    "Setting value on UIElement with id %s, value %s",
                    object_id,
                    value,
                )
            except (KeyError, NameError):
                # KeyError: A UI element may go out of scope if it was not
                # assigned to a global variable
                # NameError: UI element might not have bindings
                LOGGER.debug("Could not find UIElement with id %s", object_id)
                continue

            with self._install_execution_context(
                ui_element_registry.get_cell(object_id),
                setting_element_value=True,
            ):
                try:
                    component._update(value)
                except MarimoConvertValueException:
                    # Internal marimo error
                    sys.stderr.write(
                        "An exception was raised when updating a UIElement's "
                        "value. This is a bug in marimo. Please copy "
                        "the below traceback and paste it in an "
                        "issue: https://github.com/marimo-team/marimo/issues\n"
                    )
                    tmpio = io.StringIO()
                    traceback.print_exc(file=tmpio)
                    tmpio.seek(0)
                    sys.stderr.write(tmpio.read())
                    # Don't run referring elements of this UI element
                    continue
                except Exception:
                    # User's on_change handler an exception ...
                    sys.stderr.write(
                        "An exception was raised by a "
                        "UIElement's on_change handler:\n"
                    )

                    tmpio = io.StringIO()
                    traceback.print_exc(file=tmpio)
                    tmpio.seek(0)
                    sys.stderr.write(tmpio.read())

            bound_names = (
                name
                for name in get_context().ui_element_registry.bound_names(
                    object_id
                )
                if not is_local(name)
            )

            variable_values: list[VariableValue] = []
            for name in bound_names:
                # subtracting self.graph.definitions[name]: never rerun the
                # cell that created the name
                variable_values.append(
                    VariableValue(name=name, value=component)
                )
                try:
                    referring_cells.update(
                        self.graph.get_referring_cells(name)
                        - self.graph.get_defining_cells(name)
                    )
                except Exception:
                    # Internal marimo error
                    sys.stderr.write(
                        "An exception was raised when finding cells that "
                        f"refer to a UIElement value, for bound name {name}. "
                        "This is a bug in marimo. "
                        "Please copy the below traceback and paste it in an "
                        "issue: https://github.com/marimo-team/marimo/issues\n"
                    )
                    tmpio = io.StringIO()
                    traceback.print_exc(file=tmpio)
                    tmpio.seek(0)
                    sys.stderr.write(tmpio.read())
                    # Entering undefined behavior territory ...
                    continue

            if variable_values:
                VariableValues(variables=variable_values).broadcast()
        self._run_cells(
            dataflow.transitive_closure(self.graph, referring_cells)
        )

    def get_ui_initial_value(self, object_id: str) -> Any:
        """Get an initial value for a UIElement, if any

        Initial values are optionally populated during instantiation

        Args:
        ----
        object_id: ID of UIElement

        Returns:
        -------
        initial value of UI element, if any

        Raises:
        ------
        KeyError if object_id not found
        """
        return self.ui_initializers[object_id]

    def reset_ui_initializers(self) -> None:
        self.ui_initializers = {}

    def function_call_request(
        self, request: FunctionCallRequest
    ) -> tuple[HumanReadableStatus, JSONType]:
        function = get_context().function_registry.get_function(
            request.namespace, request.function_name
        )
        error_title, error_message = "", ""

        def debug(title: str, message: str) -> None:
            LOGGER.debug("%s: %s", title, message)

        if function is None:
            error_title = "Function not found"
            error_message = (
                "Could not find function given request: %s" % request
            )
            debug(error_title, error_message)
        elif function.cell_id is None:
            error_title = "Function not associated with cell"
            error_message = (
                "Attempted to call a function without a cell id: %s" % request
            )
            debug(error_title, error_message)
        else:
            with self._install_execution_context(cell_id=function.cell_id):
                try:
                    return HumanReadableStatus(code="ok"), function(
                        request.args
                    )
                except MarimoInterrupt:
                    error_title = "Interrupted"
                    error_message = (
                        "Function call (%s) was interrupted by the user"
                        % request.function_name
                    )
                    debug(error_title, error_message)
                except Exception as e:
                    error_title = "Exception"
                    error_message = (
                        "Function call (name: %s, args: %s) failed with exception %s"  # noqa: E501
                        % (request.function_name, request.args, str(e))
                    )
                    debug(error_title, error_message)
        # Couldn't call function, or function call failed
        return (
            HumanReadableStatus(
                code="error", title=error_title, message=error_message
            ),
            None,
        )

    def instantiate(self, request: CreationRequest) -> None:
        """Instantiate the kernel with cells and UIElement initial values

        During instantiation, UIElements can check for an initial value
        with `get_initial_value`
        """
        if self.graph.cells:
            del request
            LOGGER.debug("App already instantiated.")
        else:
            self.reset_ui_initializers()
            for (
                object_id,
                initial_value,
            ) in request.set_ui_element_value_request.ids_and_values:
                self.ui_initializers[object_id] = initial_value
            self.run(request.execution_requests)
            self.reset_ui_initializers()


def launch_kernel(
    control_queue: QueueType[ControlRequest],
    completion_queue: QueueType[CompletionRequest],
    input_queue: QueueType[str],
    socket_addr: tuple[str, int],
    is_edit_mode: bool,
    configs: dict[CellId_t, CellConfig],
    app_metadata: AppMetadata,
) -> None:
    LOGGER.debug("Launching kernel")
    if is_edit_mode:
        restore_signals()

    n_tries = 0
    pipe: Optional[TypedConnection[KernelMessage]] = None
    while n_tries < 100:
        try:
            pipe = TypedConnection[KernelMessage].of(
                mp.connection.Client(socket_addr)
            )
            break
        except Exception:
            n_tries += 1
            time.sleep(0.01)

    if n_tries == 100 or pipe is None:
        LOGGER.debug("Failed to connect to socket.")
        return

    # Create communication channels
    stream = ThreadSafeStream(pipe=pipe, input_queue=input_queue)
    # Console output is hidden in run mode, so no need to redirect
    # (redirection of console outputs is not thread-safe anyway)
    stdout = ThreadSafeStdout(stream) if is_edit_mode else None
    stderr = ThreadSafeStderr(stream) if is_edit_mode else None
    # TODO(akshayka): stdin in run mode? input(prompt) uses stdout, which
    # isn't currently available in run mode.
    stdin = ThreadSafeStdin(stream) if is_edit_mode else None

    kernel = Kernel(
        cell_configs=configs,
        app_metadata=app_metadata,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
        input_override=input_override,
    )
    initialize_context(
        kernel=kernel,
        stream=stream,
    )

    if is_edit_mode:
        # completions only provided in edit mode
        kernel.start_completion_worker(completion_queue)

        # In edit mode, kernel runs in its own process so it's interruptible.
        from marimo._output.formatters.formatters import register_formatters

        # TODO: Windows workaround -- find a way to make the process
        # its group leader
        if sys.platform != "win32":
            # Make this process group leader to prevent it from receiving
            # signals intended for the parent (server) process,
            # Ctrl+C in particular.
            os.setsid()

        # kernels are processes in edit mode, and each process needs to
        # install the formatter import hooks
        register_formatters()

        SHUTTING_DOWN = False

        def interrupt_handler(signum: int, frame: Any) -> None:
            """Tries to interrupt the kernel."""
            del signum
            del frame

            LOGGER.debug("interrupt request received")
            # TODO(akshayka): if kernel is in `run` but not executing,
            # it won't be interrupted, which isn't right ... but the
            # probability of that happening is low.
            if kernel.execution_context is not None:
                Interrupted().broadcast()
                raise MarimoInterrupt

        def sigterm_handler(signum: int, frame: Any) -> None:
            """Cleans up the kernel ands exit."""
            del signum
            del frame

            nonlocal SHUTTING_DOWN
            if SHUTTING_DOWN:
                # give previous SIGTERM a chance to quit ... makes
                # sure this method is reentrant
                return
            SHUTTING_DOWN = True

            get_context().virtual_file_registry.shutdown()
            # Force this process to exit.
            #
            # We use os._exit() instead of sys.exit() because we don't want the
            # child process to also run atexit handlers, which may result in
            # undefined behavior. Using sys.exit() on Linux sometimes causes
            # the parent process to hang on shutdown, leading to orphaned
            # processes and port.
            #
            # TODO(akshayka): The Python docs say this method is appropriate
            # for processes created with fork(), but they don't say anything
            # about processes made with spawn. macOS and Windows default to
            # spawn. If we have further issues with clean exits, we might
            # investigate here.
            #
            # https://docs.python.org/3/library/os.html#os._exit
            # https://www.unixguide.net/unix/programming/1.1.3.shtml
            os._exit(0)

        signal.signal(signal.SIGINT, interrupt_handler)

        if sys.platform == "win32" or sys.platform == "cygwin":
            # windows doesn't handle SIGTERM
            signal.signal(signal.SIGBREAK, sigterm_handler)
        else:
            signal.signal(signal.SIGTERM, sigterm_handler)

    while True:
        try:
            request = control_queue.get()
        except Exception as e:
            # triggered on Windows when quit with Ctrl+C
            LOGGER.debug("kernel queue.get() failed %s", e)
            break
        LOGGER.debug("received request %s", request)
        if isinstance(request, CreationRequest):
            kernel.instantiate(request)
            CompletedRun().broadcast()
        elif isinstance(request, ExecuteMultipleRequest):
            kernel.run(request.execution_requests)
            CompletedRun().broadcast()
        elif isinstance(request, SetCellConfigRequest):
            kernel.set_cell_config(request)
        elif isinstance(request, SetUIElementValueRequest):
            kernel.set_ui_element_value(request)
            CompletedRun().broadcast()
        elif isinstance(request, FunctionCallRequest):
            status, ret = kernel.function_call_request(request)
            FunctionCallResult(
                function_call_id=request.function_call_id,
                return_value=ret,
                status=status,
            ).broadcast()
            CompletedRun().broadcast()
        elif isinstance(request, DeleteRequest):
            kernel.delete(request)
        elif isinstance(request, StopRequest):
            break
        else:
            raise ValueError(f"Unknown request {request}")

    if stdout is not None and isinstance(stdout, ThreadSafeStdout):
        stdout._watcher.stop()
    if stderr is not None and isinstance(stderr, ThreadSafeStderr):
        stderr._watcher.stop()
    get_context().virtual_file_registry.shutdown()
