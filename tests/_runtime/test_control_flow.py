# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime import control_flow
from marimo._runtime.commands import ExecuteCellCommand
from marimo._runtime.runner import cell_runner
from marimo._runtime.runner.hooks import NotebookCellHooks
from marimo._runtime.runtime import Kernel


async def test_stop_false(execution_kernel: Kernel) -> None:
    k = execution_kernel
    await k.run(
        [
            ExecuteCellCommand(
                cell_id="0",
                code="import marimo as mo; x = 0; mo.stop(False); y = 1",
            ),
            ExecuteCellCommand(cell_id="1", code="z = y + 1"),
        ]
    )
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert k.globals["z"] == 2


async def test_stop_true(execution_kernel: Kernel) -> None:
    k = execution_kernel
    # Populate the kernel and its globals
    await k.run(
        [
            ExecuteCellCommand(cell_id="0", code="x = 0; y = 1"),
            ExecuteCellCommand(cell_id="1", code="z = y + 1"),
        ]
    )
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert k.globals["z"] == 2

    # Force cell 0 to stop
    await k.run(
        [
            ExecuteCellCommand(
                cell_id="0",
                code="import marimo as mo; x = 0; mo.stop(True); y = 1",
            ),
        ]
    )
    # stop happened after x was assigned, so it should still exist
    assert k.globals["x"] == 0
    # y is assigned after stop, so it should not exist
    assert "y" not in k.globals
    # cell 1's defs should be invalidated
    assert "z" not in k.globals


async def test_stop_output(execution_kernel: Kernel) -> None:
    k = execution_kernel
    # Run a cell through the kernel to populate graph
    await k.run(
        [
            ExecuteCellCommand(
                cell_id="0",
                code="import marimo as mo; x = 0; mo.stop(True, 'stopped!'); y = 1",
            ),
        ]
    )
    # Run the cell through the runner to get the output
    runner = cell_runner.Runner(
        set(["0"]),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
        hooks=NotebookCellHooks(),
    )
    run_result = await runner.run("0")
    # Check that the cell was stopped and its output is the stop output
    assert run_result.output == "stopped!"
    assert isinstance(run_result.exception, control_flow.MarimoStopError)
