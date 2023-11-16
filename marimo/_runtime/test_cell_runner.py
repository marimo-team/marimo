# Copyright 2023 Marimo. All rights reserved.
from marimo._runtime.cell_runner import Runner
from marimo._runtime.conftest import ExecReqProvider
from marimo._runtime.runtime import Kernel


def test_cell_output(k: Kernel, exec_req: ExecReqProvider) -> None:
    # run the cell to populate the graph, globals
    k.run([er := exec_req.get("'hello'; 123")])

    runner = Runner(
        cell_ids=set(k.graph.cells.keys()), graph=k.graph, glbls=k.globals
    )
    run_result = runner.run(er.cell_id)
    # last expression of cell is output
    assert run_result.output == 123
