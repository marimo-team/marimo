# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Callable

from marimo import _loggers
from marimo._ast.cell import CellImpl
from marimo._ast.toplevel import TopLevelExtraction
from marimo._data.get_datasets import (
    get_datasets_from_variables,
    has_updates_to_datasource,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.errors import (
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
    MarimoStrictExecutionError,
)
from marimo._messaging.ops import (
    CellOp,
    Datasets,
    DataSourceConnections,
    VariableValue,
    VariableValues,
)
from marimo._messaging.tracebacks import write_traceback
from marimo._output import formatting
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import get_context, get_global_context
from marimo._runtime.control_flow import MarimoInterrupt, MarimoStopError
from marimo._runtime.runner import cell_runner
from marimo._runtime.side_effect import SideEffect
from marimo._server.model import SessionMode
from marimo._sql.engines.duckdb import (
    INTERNAL_DUCKDB_ENGINE,
    DuckDBEngine,
)
from marimo._sql.get_engines import (
    engine_to_data_source_connection,
    get_engines_from_variables,
)
from marimo._tracer import kernel_tracer
from marimo._types.ids import VariableName
from marimo._utils.flatten import contains_instance

LOGGER = _loggers.marimo_logger()


PostExecutionHookType = Callable[
    [CellImpl, cell_runner.Runner, cell_runner.RunResult], None
]


@kernel_tracer.start_as_current_span("set_imported_defs")
def _set_imported_defs(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    del run_result
    LOGGER.debug("Acquiring graph lock to update cell import workspace")
    with runner.graph.lock:
        LOGGER.debug("Acquired graph lock to update import workspace.")
        if cell.import_workspace.is_import_block:
            cell.import_workspace.imported_defs = set(
                name for name in cell.defs if name in runner.glbls
            )


@kernel_tracer.start_as_current_span("set_status_idle")
def _set_status_idle(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    del run_result
    del runner
    cell.set_runtime_state(status="idle")


@kernel_tracer.start_as_current_span("set_run_result_status")
def _set_run_result_status(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    if isinstance(run_result.exception, MarimoInterruptionError):
        cell.set_run_result_status("interrupted")
    elif runner.cancelled(cell.cell_id):
        cell.set_run_result_status("cancelled")
    elif run_result.exception is not None:
        cell.set_run_result_status("exception")
    else:
        cell.set_run_result_status("success")


@kernel_tracer.start_as_current_span("broadcast_variables")
def _broadcast_variables(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    # Skip if not in edit mode
    if not _is_edit_mode():
        return

    del run_result
    values = [
        VariableValue(
            name=variable,
            value=(
                runner.glbls[variable] if variable in runner.glbls else None
            ),
        )
        for variable in cell.defs
    ]
    if values:
        VariableValues(variables=values).broadcast()


@kernel_tracer.start_as_current_span("broadcast_datasets")
def _broadcast_datasets(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    # Skip if not in edit mode
    if not _is_edit_mode():
        return

    del run_result
    tables = get_datasets_from_variables(
        [
            (VariableName(variable), runner.glbls[variable])
            for variable in cell.defs
            if variable in runner.glbls
        ]
    )
    if tables:
        LOGGER.debug("Broadcasting data tables")
        Datasets(tables=tables).broadcast()


@kernel_tracer.start_as_current_span("broadcast_data_source_connection")
def _broadcast_data_source_connection(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    # Skip if not in edit mode
    if not _is_edit_mode():
        return

    del run_result
    engines = get_engines_from_variables(
        [
            (VariableName(variable), runner.glbls[variable])
            for variable in cell.defs
            if variable in runner.glbls
        ]
    )

    if not engines:
        return

    LOGGER.debug("Broadcasting data source connections")
    DataSourceConnections(
        connections=[
            engine_to_data_source_connection(variable, engine)
            for variable, engine in engines
        ]
    ).broadcast()


@kernel_tracer.start_as_current_span("broadcast_duckdb_datasource")
def _broadcast_duckdb_datasource(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    # Skip if not in edit mode
    if not _is_edit_mode():
        return

    del run_result
    del runner
    if not DependencyManager.duckdb.has():
        return

    try:
        sqls = cell.sqls
        if not sqls:
            return
        modifies_datasources = any(
            has_updates_to_datasource(sql) for sql in sqls
        )
        if not modifies_datasources:
            return

        LOGGER.debug("Broadcasting internal duckdb datasource")
        DataSourceConnections(
            connections=[
                engine_to_data_source_connection(
                    INTERNAL_DUCKDB_ENGINE, DuckDBEngine()
                )
            ]
        ).broadcast()
    except Exception:
        return


@kernel_tracer.start_as_current_span("store_reference_to_output")
def _store_reference_to_output(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    del runner

    # Stores a reference to the output if it contains a UIElement;
    # this is required to make RPCs work for unnamed UI elements.
    if isinstance(run_result.output, UIElement):
        cell.set_output(run_result.output)
    elif run_result.output is not None:
        if contains_instance(run_result.output, UIElement):
            cell.set_output(run_result.output)


def _store_state_reference(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    del run_result
    # Associate state variables with variable names
    ctx = get_context()
    ctx.state_registry.register_scope(runner.glbls, defs=cell.defs)
    privates = set().union(
        *[cell.temporaries for cell in ctx.graph.cells.values()]
    )
    ctx.state_registry.retain_active_states(
        set(runner.graph.definitions.keys()) | privates
    )


@kernel_tracer.start_as_current_span("issue_exception_side_effect")
def _issue_exception_side_effect(
    _cell: CellImpl,
    _runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    ctx = get_context()
    if run_result.exception is not None:
        exception = run_result.exception
        key = type(exception).__name__
        traceback = getattr(exception, "__traceback__", None)
        if traceback:
            # Side effect hash is the exception name
            # AND the instruction pointer.
            # Side effect has to be relatively robust to code changes
            #  - Bars line number since comments should not effect
            #  - Bars stacktrace since file path should be agnostic
            # Code content is already utilized in hash, and tb_lasti is the
            # bytecode instruction pointer. So if the code is the same, then the
            # difference can be captured by where in the evaluation the exception
            # was raised.
            key += f":{traceback.tb_lasti}"
        # NB. This is on a cell level.
        ctx.cell_lifecycle_registry.add(SideEffect(key))


@kernel_tracer.start_as_current_span("broadcast_outputs")
def _broadcast_outputs(
    cell: CellImpl,
    _runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    # TODO: clean this logic up ...
    #
    # Send the output to the frontend
    #
    # Don't rebroadcast an output that was already sent
    #
    # 1. if run_result.output is not None, need to send it
    # 2. otherwise if exc_ctx.output is None, then need to send
    #    the (empty) output (to clear it)
    should_send_output = (
        run_result.output is not None or run_result.accumulated_output is None
    )
    if (
        run_result.success()
        or isinstance(run_result.exception, MarimoStopError)
    ) and should_send_output:
        formatted_output = formatting.try_format(run_result.output)
        if formatted_output.exception is not None:
            # Try a plain formatter; maybe an opinionated one failed.
            formatted_output = formatting.try_format(
                run_result.output, include_opinionated=False
            )
        if formatted_output.traceback is not None:
            write_traceback(formatted_output.traceback)

        CellOp.broadcast_output(
            channel=CellChannel.OUTPUT,
            mimetype=formatted_output.mimetype,
            data=formatted_output.data,
            cell_id=cell.cell_id,
            status=None,
        )
    elif isinstance(run_result.exception, MarimoStrictExecutionError):
        LOGGER.debug("Cell %s raised a strict error", cell.cell_id)
        # Cell never runs, so clear console
        CellOp.broadcast_error(
            data=[run_result.output],
            clear_console=True,
            cell_id=cell.cell_id,
        )
    elif isinstance(run_result.exception, MarimoInterrupt):
        LOGGER.debug("Cell %s was interrupted", cell.cell_id)
        # don't clear console because this cell was running and
        # its console outputs are not stale
        CellOp.broadcast_error(
            data=[MarimoInterruptionError()],
            clear_console=False,
            cell_id=cell.cell_id,
        )
    elif isinstance(run_result.exception, MarimoExceptionRaisedError):
        CellOp.broadcast_error(
            data=[run_result.exception],
            clear_console=False,
            cell_id=cell.cell_id,
        )
    elif run_result.exception is not None:
        LOGGER.debug(
            "Cell %s raised %s",
            cell.cell_id,
            type(run_result.exception).__name__,
        )
        # don't clear console because this cell was running and
        # its console outputs are not stale
        exception_type = type(run_result.exception).__name__
        msg = str(run_result.exception)
        if not msg:
            msg = f"This cell raised an exception: {exception_type}"
        CellOp.broadcast_error(
            data=[
                MarimoExceptionRaisedError(
                    msg=msg,
                    exception_type=exception_type,
                    raising_cell=None,
                )
            ],
            clear_console=False,
            cell_id=cell.cell_id,
        )


@kernel_tracer.start_as_current_span("render_toplevel_defs")
def render_toplevel_defs(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    del run_result
    variable = cell.toplevel_variable
    if variable is not None:
        extractor = TopLevelExtraction.from_graph(cell, runner.graph)
        serialization = list(iter(extractor))[-1]
        CellOp.broadcast_serialization(
            serialization=serialization,
            cell_id=cell.cell_id,
        )


@kernel_tracer.start_as_current_span("run_pytest")
def attempt_pytest(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    del run_result
    if cell._test:
        try:
            import marimo._runtime.pytest as marimo_pytest

            if runner.execution_context is not None:
                with runner.execution_context(cell.cell_id):
                    result = marimo_pytest.run_pytest(cell.defs, runner.glbls)
                    if result.output:
                        sys.stdout.write(result.output)
        except ImportError:
            pass


@kernel_tracer.start_as_current_span("reset_matplotlib_context")
def _reset_matplotlib_context(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    del cell
    del run_result
    if get_global_context().mpl_installed:
        # ensures that every cell gets a fresh axis.
        exec("__marimo__._output.mpl.close_figures()", runner.glbls)


def _is_edit_mode() -> bool:
    ctx = get_context()
    return (
        isinstance(ctx, KernelRuntimeContext)
        and ctx.session_mode == SessionMode.EDIT
    )


POST_EXECUTION_HOOKS: list[PostExecutionHookType] = [
    _set_imported_defs,
    _set_run_result_status,
    _store_reference_to_output,
    _store_state_reference,
    _issue_exception_side_effect,
    _broadcast_variables,
    _broadcast_datasets,
    _broadcast_data_source_connection,
    _broadcast_duckdb_datasource,
    _broadcast_outputs,
    _reset_matplotlib_context,
    # set status to idle after all post-processing is done, in case the
    # other hooks take a long time (broadcast outputs can take a long time
    # if a formatter is slow).
    _set_status_idle,
    # NB. Other hooks are added ad-hoc or manually due to priority.
    # Consider implementing priority sort to keep everything more centralized.
]
