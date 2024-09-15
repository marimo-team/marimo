# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable

from marimo._ast.cell import CellImpl
from marimo._runtime.runner import cell_runner
from marimo._tracer import kernel_tracer

PreExecutionHookType = Callable[[CellImpl, cell_runner.Runner], None]


@kernel_tracer.start_as_current_span("set_staleness")
def _set_staleness(
    cell: CellImpl,
    runner: cell_runner.Runner,
) -> None:
    graph = runner.graph

    if runner.execution_mode == "lazy" and not graph.is_any_ancestor_stale(
        cell.cell_id
    ):
        # TODO: The above check could be omitted as an optimization as long as
        # parents are guaranteed to run before child.
        #
        # Only no longer stale if its parents are not stale
        cell.set_stale(stale=False)


@kernel_tracer.start_as_current_span("set_status_to_running")
def _set_status_to_running(
    cell: CellImpl,
    runner: cell_runner.Runner,
) -> None:
    del runner
    cell.set_runtime_state("running")


PRE_EXECUTION_HOOKS: list[PreExecutionHookType] = [
    _set_staleness,
    _set_status_to_running,
]
