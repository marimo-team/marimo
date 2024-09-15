# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable

from marimo import _loggers
from marimo._messaging.errors import (
    Error,
    MarimoAncestorPreventedError,
    MarimoAncestorStoppedError,
    MarimoExceptionRaisedError,
    MarimoInterruptionError,
    MarimoStrictExecutionError,
)
from marimo._messaging.ops import CellOp
from marimo._runtime.control_flow import MarimoStopError
from marimo._runtime.runner import cell_runner
from marimo._tracer import kernel_tracer

LOGGER = _loggers.marimo_logger()

OnFinishHookType = Callable[[cell_runner.Runner], None]


@kernel_tracer.start_as_current_span("send_interrupt_errors")
def _send_interrupt_errors(runner: cell_runner.Runner) -> None:
    if runner.cells_to_run:
        assert runner.interrupted
        for cid in runner.cells_to_run:
            # `cid` was not run
            runner.graph.cells[cid].set_runtime_state("idle")
            CellOp.broadcast_error(
                data=[MarimoInterruptionError()],
                # these cells are transitioning from queued to stopped
                # (interrupted); they didn't get to run, so their consoles
                # reflect a previous run and should be cleared
                clear_console=True,
                cell_id=cid,
            )


@kernel_tracer.start_as_current_span("send_cancellation_errors")
def _send_cancellation_errors(runner: cell_runner.Runner) -> None:
    for raising_cell in runner.cells_cancelled:
        for cid in runner.cells_cancelled[raising_cell]:
            # `cid` was not run
            cell = runner.graph.cells[cid]
            if cell.runtime_state != "idle":
                # the cell raising an exception will already be
                # idle, but its descendants won't be.
                cell.set_runtime_state("idle")

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
            elif isinstance(exception, MarimoStrictExecutionError):
                data = MarimoAncestorPreventedError(
                    msg=(
                        "This cell wasn't run because an "
                        f"ancestor failed to resolve the "
                        f"reference `{exception.ref}` : "
                    ),
                    raising_cell=raising_cell,
                    blamed_cell=exception.blamed_cell,
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
            )


ON_FINISH_HOOKS: list[OnFinishHookType] = [
    _send_interrupt_errors,
    _send_cancellation_errors,
]
