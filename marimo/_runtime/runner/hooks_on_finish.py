# Copyright 2024 Marimo. All rights reserved.
from marimo import _loggers
from marimo._messaging.errors import (
    Error,
    MarimoAncestorStoppedError,
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
)
from marimo._messaging.ops import CellOp
from marimo._runtime.control_flow import MarimoStopError
from marimo._runtime.runner import cell_runner

LOGGER = _loggers.marimo_logger()


def _send_interrupt_errors(runner: cell_runner.Runner) -> None:
    if runner.cells_to_run:
        assert runner.interrupted
        for cid in runner.cells_to_run:
            # `cid` was not run
            runner.graph.cells[cid].set_status("idle")
            CellOp.broadcast_error(
                data=[MarimoInterruptionError()],
                # these cells are transitioning from queued to stopped
                # (interrupted); they didn't get to run, so their consoles
                # reflect a previous run and should be cleared
                clear_console=True,
                cell_id=cid,
                status="idle",
            )


def _send_cancellation_errors(runner: cell_runner.Runner) -> None:
    for raising_cell in runner.cells_cancelled:
        for cid in runner.cells_cancelled[raising_cell]:
            # `cid` was not run
            runner.graph.cells[cid].set_status("idle")
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
                exception_type = type(runner.exceptions[raising_cell]).__name__
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


ON_FINISH_HOOKS = [_send_interrupt_errors, _send_cancellation_errors]
