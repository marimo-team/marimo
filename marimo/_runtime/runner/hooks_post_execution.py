# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable

from marimo import _loggers
from marimo._ast.cell import CellImpl
from marimo._data.get_datasets import (
    get_datasets_from_duckdb,
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
    VariableValue,
    VariableValues,
)
from marimo._messaging.tracebacks import write_traceback
from marimo._output import formatting
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context.types import get_global_context
from marimo._runtime.control_flow import MarimoInterrupt, MarimoStopError
from marimo._runtime.runner import cell_runner
from marimo._tracer import kernel_tracer
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
    del run_result
    tables = get_datasets_from_variables(
        [
            (variable, runner.glbls[variable])
            for variable in cell.defs
            if variable in runner.glbls
        ]
    )
    if tables:
        LOGGER.debug("Broadcasting data tables")
        Datasets(tables=tables).broadcast()


@kernel_tracer.start_as_current_span("broadcast_duckdb_tables")
def _broadcast_duckdb_tables(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
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

        tables = get_datasets_from_duckdb()
        if not tables:
            return

        LOGGER.debug("Broadcasting duckdb tables")
        Datasets(tables=tables, clear_channel="duckdb").broadcast()
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


@kernel_tracer.start_as_current_span("broadcast_outputs")
def _broadcast_outputs(
    cell: CellImpl,
    runner: cell_runner.Runner,
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

        def format_output() -> formatting.FormattedOutput:
            formatted_output = formatting.try_format(run_result.output)

            if formatted_output.exception is not None:
                # Try a plain formatter; maybe an opinionated one failed.
                formatted_output = formatting.try_format(
                    run_result.output, include_opinionated=False
                )

            if formatted_output.traceback is not None:
                write_traceback(formatted_output.traceback)
            return formatted_output

        if runner.execution_context is not None:
            with runner.execution_context(cell.cell_id):
                formatted_output = format_output()
        else:
            formatted_output = format_output()

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
            cell_id=cell.cell_id,
        )


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


POST_EXECUTION_HOOKS: list[PostExecutionHookType] = [
    _set_imported_defs,
    _set_run_result_status,
    _store_reference_to_output,
    _broadcast_variables,
    _broadcast_datasets,
    _broadcast_duckdb_tables,
    _broadcast_outputs,
    _reset_matplotlib_context,
    # set status to idle after all post-processing is done, in case the
    # other hooks take a long time (broadcast outputs can take a long time
    # if a formatter is slow).
    _set_status_idle,
]
