# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import builtins
import contextlib
import io
import itertools
import multiprocessing as mp
import queue
import signal
import sys
import threading
import time
import traceback
from collections.abc import Iterable, Sequence
from queue import Empty as QueueEmpty
from typing import Any, Iterator, Optional

from marimo import _loggers
from marimo._ast.cell import CellId_t, parse_cell
from marimo._messaging.errors import (
    Error,
    MarimoAncestorStoppedError,
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
    MarimoSyntaxError,
    UnknownError,
)
from marimo._messaging.messages import (
    write_completed_run,
    write_interrupted,
    write_marimo_error,
    write_new_run,
    write_output,
    write_queued,
    write_remove_ui_elements,
)
from marimo._messaging.streams import Stderr, Stdout, Stream, redirect_streams
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.registry import UIElementRegistry
from marimo._runtime import cell_runner, dataflow
from marimo._runtime.complete import complete
from marimo._runtime.context import (
    get_context,
    get_global_context,
    initialize_context,
)
from marimo._runtime.control_flow import MarimoInterrupt, MarimoStopError
from marimo._runtime.requests import (
    CompletionRequest,
    ConfigurationRequest,
    CreationRequest,
    DeleteRequest,
    ExecuteMultipleRequest,
    ExecutionRequest,
    Request,
    SetUIElementValueRequest,
    StopRequest,
)
from marimo._runtime.validate_graph import check_for_errors
from marimo.config._config import configure

LOGGER = _loggers.marimo_logger()


@mddoc
def defs() -> tuple[str, ...]:
    """Get the definitions of the currently executing cell.

    **Returns**:

    - tuple of the currently executing cell's defs.
    """
    ctx = get_context()
    if ctx.initialized and ctx.kernel.cell_id is not None:
        return tuple(
            sorted(
                defn
                for defn in ctx.kernel.graph.cells[ctx.kernel.cell_id].defs
            )
        )
    return tuple()


@mddoc
def refs() -> tuple[str, ...]:
    """Get the references of the currently executing cell.

    **Returns**:

    - tuple of the currently executing cell's refs.
    """
    ctx = get_context()
    # builtins that have not been shadowed by the user
    unshadowed_builtins = set(builtins.__dict__.keys()).difference(
        set(ctx.kernel.graph.definitions.keys())
    )
    if ctx.initialized and ctx.kernel.cell_id is not None:
        return tuple(
            sorted(
                defn
                for defn in ctx.kernel.graph.cells[ctx.kernel.cell_id].refs
                # exclude builtins that have not been shadowed
                if defn not in unshadowed_builtins
            )
        )
    return tuple()


class Kernel:
    def __init__(self) -> None:
        self.globals: dict[Any, Any] = {
            "__name__": "__main__",
            "__builtins__": globals()["__builtins__"],
        }
        self.graph = dataflow.DirectedGraph()
        self.executing = False
        self.cell_id: Optional[CellId_t] = None
        self.ui_initializers: dict[str, Any] = {}
        self.errors: dict[CellId_t, tuple[Error, ...]] = {}

        self.completion_thread: Optional[threading.Thread] = None
        self.completion_queue: queue.Queue[CompletionRequest] = queue.Queue()

        # an empty string represents the current directory
        exec("import sys; sys.path.append('')", self.globals)
        exec("import marimo as __marimo__", self.globals)

    @contextlib.contextmanager
    def _execution_ctx(self, cell_id: CellId_t) -> Iterator[None]:
        self.executing = True
        self.cell_id = cell_id
        with get_context().provide_ui_ids(str(cell_id)), redirect_streams(
            cell_id
        ):
            try:
                yield
            finally:
                self.executing = False
                self.cell_id = None

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
            cell = parse_cell(
                code, cell_runner.cell_filename(cell_id), cell_id
            )
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
                previous_children = self._delete_cell(cell_id)
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
        self, names: Iterable[str], exclude_defs: set[str]
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
        self, cell_id: CellId_t, exclude_defs: Optional[set[str]] = None
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
        write_remove_ui_elements(cell_id)

    def _delete_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Delete a cell from the kernel and the graph.

        Deletion from the kernel involves removing cell's defs and
        de-registering its UI Elements.

        Deletion from graph is forwarded to graph object.
        """
        if cell_id not in self.errors:
            self._invalidate_cell_state(cell_id)
            return self.graph.delete_cell(cell_id)
        else:
            # An errored cell can be thought of as a cell that's in the graph
            # but that has no state in the kernel (because it was never run).
            # Its defs may overlap with defs of a non-errored cell, so we MUST
            # NOT delete/cleanup its defs from the kernel.
            self.graph.delete_cell(cell_id)
            return set()

    def mutate_graph(
        self,
        execution_requests: Sequence[ExecutionRequest],
        deletion_requests: Sequence[DeleteRequest],
    ) -> set[CellId_t]:
        """Add and remove cells to the graph.

        This method adds the cells in `execution_requests` to the kernel's
        graph (deleting old versions of these cells, if any), and removes the
        cells in `execution_requests` from the kernel's graph.

        The mutations that this method makes to the graph renders the
        kernel inconsistent.

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
        keep_alive_defs: set[str] = set()
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
            write_marimo_error(
                data=self.errors[cid], clear_console=True, cell_id=cid
            )

        return descendants

    def _run_cells(self, cell_ids: set[CellId_t]) -> None:
        LOGGER.debug("preparing to evaluate cells %s", cell_ids)
        for cid in cell_ids:
            write_queued(cell_id=cid)

        runner = cell_runner.Runner(
            cell_ids=cell_ids, graph=self.graph, glbls=self.globals
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

            LOGGER.debug("running cell %s", cell_id)
            write_new_run(cell_id)
            # State clean-up: don't leak names, UI elements, ...
            self._invalidate_cell_state(cell_id)

            with self._execution_ctx(cell_id):
                run_result = runner.run(cell_id)

            if run_result.success():
                formatted_output = run_result.format_output()
                if formatted_output.traceback is not None:
                    with self._execution_ctx(cell_id):
                        sys.stderr.write(formatted_output.traceback)
                write_output(
                    channel=formatted_output.channel,
                    mimetype=formatted_output.mimetype,
                    data=formatted_output.data,
                    cell_id=cell_id,
                )
            elif isinstance(run_result.exception, MarimoStopError):
                LOGGER.debug("Cell %s was stopped via mo.stop()", cell_id)
                formatted_output = run_result.format_output()
                if formatted_output.traceback is not None:
                    with self._execution_ctx(cell_id):
                        sys.stderr.write(formatted_output.traceback)
                write_output(
                    channel=formatted_output.channel,
                    mimetype=formatted_output.mimetype,
                    data=formatted_output.data,
                    cell_id=cell_id,
                )
            elif isinstance(run_result.exception, MarimoInterrupt):
                LOGGER.debug("Cell %s was interrupted", cell_id)
                # don't clear console because this cell was running and
                # its console outputs are not stale
                write_marimo_error(
                    data=[MarimoInterruptionError()],
                    clear_console=False,
                    cell_id=cell_id,
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
                write_marimo_error(
                    data=[
                        MarimoExceptionRaisedError(
                            msg="This cell raised an exception: %s%s"
                            % (
                                exception_type,
                                f"('{str(run_result.exception)}')"
                                if str(run_result.exception)
                                else "",
                            ),
                            exception_type=exception_type,
                            raising_cell=None,
                        )
                    ],
                    clear_console=False,
                    cell_id=cell_id,
                )

            if get_global_context().mpl_installed:
                # ensures that every cell gets a fresh axis.
                exec("__marimo__._output.mpl.close_figures()", self.globals)

        if runner.cells_to_run:
            assert runner.interrupted
            for cid in runner.cells_to_run:
                # `cid` was not run. Its defs should be deleted.
                self._invalidate_cell_state(cid)
                write_marimo_error(
                    data=[MarimoInterruptionError()],
                    # these cells are transitioning from queued to stopped
                    # (interrupted); they didn't get to run, so their consoles
                    # reflect a previous run and should be cleared
                    clear_console=True,
                    cell_id=cid,
                )

        for raising_cell in runner.cells_cancelled:
            for cid in runner.cells_cancelled[raising_cell]:
                # `cid` was not run. Its defs should be deleted.
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
                write_marimo_error(
                    data=[data],
                    # these cells are transitioning from queued to stopped
                    # (interrupted); they didn't get to run, so their consoles
                    # reflect a previous run and should be cleared
                    clear_console=True,
                    cell_id=cid,
                )

        LOGGER.debug("Finished run.")
        write_completed_run()

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
        self._run_cells(
            self.mutate_graph(execution_requests, deletion_requests=[])
        )

    def set_ui_element_value(self, request: SetUIElementValueRequest) -> None:
        referring_cells = set()
        for object_id, value in request.ids_and_values:
            try:
                component = get_context().ui_element_registry.get_object(
                    object_id
                )
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

            component._update(value)
            bound_names = get_context().ui_element_registry.bound_names(
                object_id
            )
            for name in bound_names:
                # subtracting self.graph.definitions[name]: never rerun the
                # cell that created the name
                referring_cells.update(
                    self.graph.get_referring_cells(name)
                    - self.graph.definitions[name]
                )
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

    def complete(self, request: CompletionRequest) -> None:
        if self.completion_thread is None:
            self.completion_thread = threading.Thread(
                target=complete,
                args=(self.completion_queue, self.graph, get_context().stream),
            )
            self.completion_thread.start()

        self.completion_queue.put(request)

    def instantiate(self, request: CreationRequest) -> None:
        """Instantiate the kernel with cells and UIElement initial values

        During instantiation, UIElements can check for an initial value
        with `get_initial_value`
        """
        if self.graph.cells:
            del request
            LOGGER.debug("App already instantiated.")
            write_completed_run()
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
    execution_queue: mp.Queue[Request] | queue.Queue[Request],
    socket_addr: tuple[str, int],
    is_edit_mode: bool,
) -> None:
    LOGGER.debug("Launching kernel")

    n_tries = 0
    while n_tries < 100:
        try:
            pipe = mp.connection.Client(socket_addr)
            break
        except Exception:
            n_tries += 1
            time.sleep(0.01)

    if n_tries == 100:
        LOGGER.debug("Failed to connect to socket.")
        return

    # Create communication channels
    stream = Stream(pipe)
    # Console output is hidden in run mode, so no need to redirect
    # (redirection of console outputs is not thread-safe anyway)
    stdout = Stdout(stream) if is_edit_mode else None
    stderr = Stderr(stream) if is_edit_mode else None

    kernel = Kernel()
    registry = UIElementRegistry()
    initialize_context(
        kernel=kernel,
        ui_element_registry=registry,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
    )

    if is_edit_mode:
        from marimo._output.formatters.formatters import register_formatters

        # kernels are processes in edit mode, and each process needs to
        # install the formatter import hooks
        register_formatters()

        def interrupt_handler(signum: int, frame: Any) -> None:
            """Clears the execution queue and tries to interrupt the kernel."""
            del signum
            del frame

            LOGGER.debug("interrupt request received")
            while not execution_queue.empty():
                try:
                    execution_queue.get_nowait()
                except QueueEmpty:
                    break

            # TODO(akshayka): if kernel is in `run` but not executing,
            # it won't be interrupted, which isn't right
            if kernel.executing:
                write_interrupted()
                raise MarimoInterrupt

        signal.signal(signal.SIGINT, interrupt_handler)

    while True:
        try:
            request = execution_queue.get()
        except Exception as e:
            # triggered on Windows when quit with Ctrl+C
            LOGGER.debug("kernel queue.get() failed %s", e)
            return
        LOGGER.debug("received request %s", request)
        if isinstance(request, CreationRequest):
            kernel.instantiate(request)
        elif isinstance(request, ExecuteMultipleRequest):
            kernel.run(request.execution_requests)
        elif isinstance(request, SetUIElementValueRequest):
            kernel.set_ui_element_value(request)
        elif isinstance(request, DeleteRequest):
            kernel.delete(request)
        elif isinstance(request, CompletionRequest):
            kernel.complete(request)
        elif isinstance(request, ConfigurationRequest):
            # Kernel runs in a separate process than server in edit mode,
            # and configuration is only allowed in edit mode. As of
            # writing configuration only controls frontend, so this
            # isn't actually needed. But it's helpful for debugging.
            configure(eval(request.config))
        elif isinstance(request, StopRequest):
            break
        else:
            raise ValueError(f"Unknown request {request}")
