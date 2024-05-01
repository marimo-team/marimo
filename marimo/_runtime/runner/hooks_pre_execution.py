# Copyright 2024 Marimo. All rights reserved.
from marimo._ast.cell import CellImpl
from marimo._runtime.runner import cell_runner


def _clear_stale_status(
    cell: CellImpl,
    runner: cell_runner.Runner,
) -> None:
    if runner.execution_mode == "detect" and not any(
        runner.graph.cells[cid].stale
        for cid in runner.graph.ancestors(cell.cell_id)
    ):
        # TODO: The above check could be omitted as an optimization as long as
        # parents are guaranteed to run before child.
        #
        # Only no longer stale if its parents are not stale
        cell.set_stale(stale=False)


def _set_running_status(
    cell: CellImpl,
    runner: cell_runner.Runner,
) -> None:
    del runner
    cell.set_status("running")


PRE_EXECUTION_HOOKS = [_clear_stale_status, _set_running_status]
