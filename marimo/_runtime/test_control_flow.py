# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime import cell_runner, control_flow
from marimo._runtime.requests import (
    ExecutionRequest,
)
from marimo._runtime.runtime import Kernel


def test_stop_false(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(
                "0", "import marimo as mo; x = 0; mo.stop(False); y = 1"
            ),
            ExecutionRequest("1", "z = y + 1"),
        ]
    )
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert k.globals["z"] == 2


def test_stop_true(k: Kernel) -> None:
    # Populate the kernel and its globals
    k.run(
        [
            ExecutionRequest("0", "x = 0; y = 1"),
            ExecutionRequest("1", "z = y + 1"),
        ]
    )
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert k.globals["z"] == 2

    # Force cell 0 to stop
    k.run(
        [
            ExecutionRequest(
                "0", "import marimo as mo; x = 0; mo.stop(True); y = 1"
            ),
        ]
    )
    # stop happened after x was assigned, so it should still exist
    assert k.globals["x"] == 0
    # y is assigned after stop, so it should not exist
    assert "y" not in k.globals
    # cell 1's defs should be invalidated
    assert "z" not in k.globals


def test_stop_output(k: Kernel) -> None:
    # Run a cell through the kernel to populate graph
    k.run(
        [
            ExecutionRequest(
                "0",
                "import marimo as mo; x = 0; mo.stop(True, 'stopped!'); y = 1",
            ),
        ]
    )
    # Run the cell through the runner to get the output
    runner = cell_runner.Runner(set(["0"]), k.graph, k.globals)
    run_result = runner.run("0")
    # Check that the cell was stopped and its output is the stop output
    assert run_result.output == "stopped!"
    assert isinstance(run_result.exception, control_flow.MarimoStopError)
