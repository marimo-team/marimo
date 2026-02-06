# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable

from marimo._runtime import dataflow
from marimo._runtime.runner.hook_context import PreparationHookContext
from marimo._tracer import kernel_tracer

PreparationHookType = Callable[[PreparationHookContext], None]


@kernel_tracer.start_as_current_span("update_stale_statuses")
def _update_stale_statuses(ctx: PreparationHookContext) -> None:
    graph = ctx.graph

    if ctx.execution_mode == "lazy":
        for cid in dataflow.transitive_closure(
            graph,
            set(ctx.cells_to_run),
            inclusive=False,
            relatives=dataflow.get_import_block_relatives(graph),
        ):
            graph.cells[cid].set_stale(stale=True)

    for cid in ctx.cells_to_run:
        if graph.is_disabled(cid):
            graph.cells[cid].set_stale(stale=True)
        else:
            graph.cells[cid].set_runtime_state(status="queued")
            if graph.cells[cid].stale:
                graph.cells[cid].set_stale(stale=False)


PREPARATION_HOOKS: list[PreparationHookType] = [_update_stale_statuses]
