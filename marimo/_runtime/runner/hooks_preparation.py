# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Callable

from marimo._runtime import dataflow
from marimo._runtime.dataflow import import_block_relatives
from marimo._runtime.runner import cell_runner
from marimo._tracer import kernel_tracer

PreparationHookType = Callable[[cell_runner.Runner], None]


@kernel_tracer.start_as_current_span("update_stale_statuses")
def _update_stale_statuses(runner: cell_runner.Runner) -> None:
    graph = runner.graph

    if runner.execution_mode == "lazy":
        for cid in dataflow.transitive_closure(
            graph,
            set(runner.cells_to_run),
            inclusive=False,
            relatives=import_block_relatives,
        ):
            graph.cells[cid].set_stale(stale=True)

    for cid in runner.cells_to_run:
        if graph.is_disabled(cid):
            graph.cells[cid].set_stale(stale=True)
        else:
            graph.cells[cid].set_runtime_state(status="queued")
            if graph.cells[cid].stale:
                if runner.execution_mode == "autorun":
                    graph.cells[cid].set_stale(stale=False)


PREPARATION_HOOKS: list[PreparationHookType] = [_update_stale_statuses]
