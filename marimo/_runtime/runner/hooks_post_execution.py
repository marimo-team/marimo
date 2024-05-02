# Copyright 2024 Marimo. All rights reserved.
from marimo import _loggers
from marimo._ast.cell import CellImpl
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.errors import (
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
)
from marimo._messaging.ops import CellOp, VariableValue, VariableValues
from marimo._messaging.tracebacks import write_traceback
from marimo._output import formatting
from marimo._runtime.context.types import get_global_context
from marimo._runtime.control_flow import MarimoInterrupt, MarimoStopError
from marimo._runtime.runner import cell_runner

LOGGER = _loggers.marimo_logger()


def _set_status_idle(
    cell: CellImpl,
    runner: cell_runner.Runner,
    run_result: cell_runner.RunResult,
) -> None:
    del run_result
    del runner
    cell.set_status(status="idle")


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
            status=cell.status,
        )
    elif isinstance(run_result.exception, MarimoInterrupt):
        LOGGER.debug("Cell %s was interrupted", cell.cell_id)
        # don't clear console because this cell was running and
        # its console outputs are not stale
        CellOp.broadcast_error(
            data=[MarimoInterruptionError()],
            clear_console=False,
            cell_id=cell.cell_id,
            status=cell.status,
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
            status=cell.status,
        )


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


POST_EXECUTION_HOOKS = [
    _set_status_idle,
    _broadcast_variables,
    _broadcast_outputs,
    _reset_matplotlib_context,
]
