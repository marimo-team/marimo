# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import CellImpl
from marimo._runtime.runner.hook_context import PreExecutionHookContext
from marimo._runtime.runner.hooks import PreExecutionHook
from marimo._tracer import kernel_tracer


@kernel_tracer.start_as_current_span("set_staleness")
def _set_staleness(
    cell: CellImpl,
    ctx: PreExecutionHookContext,
) -> None:
    graph = ctx.graph

    if ctx.execution_mode == "lazy" and not graph.is_any_ancestor_stale(
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
    ctx: PreExecutionHookContext,
) -> None:
    del ctx
    cell.set_runtime_state("running")


PRE_EXECUTION_HOOKS: list[PreExecutionHook] = [
    _set_staleness,
    _set_status_to_running,
]
