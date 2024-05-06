# Copyright 2024 Marimo. All rights reserved.
from marimo._runtime import dataflow
from marimo._runtime.runner import cell_runner


def _update_stale_statuses(runner: cell_runner.Runner) -> None:
    graph = runner.graph

    if runner.execution_mode == "lazy":
        for cid in dataflow.transitive_closure(
            graph, set(runner.cells_to_run), inclusive=False
        ):
            graph.cells[cid].set_stale(stale=True)

    for cid in runner.cells_to_run:
        if graph.is_disabled(cid):
            graph.cells[cid].set_stale(stale=True)
        else:
            graph.cells[cid].set_status(status="queued")
            if graph.cells[cid].stale:
                if runner.execution_mode == "autorun":
                    graph.cells[cid].set_stale(stale=False)


PREPARATION_HOOKS = [_update_stale_statuses]
