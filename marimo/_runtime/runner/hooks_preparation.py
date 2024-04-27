# Copyright 2024 Marimo. All rights reserved.
from marimo._runtime import dataflow
from marimo._runtime.runner import cell_runner


def _update_stale_statuses(runner: cell_runner.Runner) -> None:
    if runner.execution_mode == "detect":
        for cid in dataflow.transitive_closure(
            runner.graph, set(runner.cells_to_run), inclusive=False
        ):
            runner.graph.cells[cid].set_stale(stale=True)

    for cid in runner.cells_to_run:
        if runner.graph.is_disabled(cid):
            runner.graph.cells[cid].set_stale(stale=True)
        else:
            runner.graph.cells[cid].set_status(status="queued")
            if runner.graph.cells[cid].stale:
                if runner.execution_mode == "autorun":
                    runner.graph.cells[cid].set_stale(stale=False)


PREPARATION_HOOKS = [_update_stale_statuses]
