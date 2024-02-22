# Copyright 2024 Marimo. All rights reserved.
from marimo._runtime.capture import capture_stderr
from marimo._runtime.cell_runner import Runner
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_cell_output(k: Kernel, exec_req: ExecReqProvider) -> None:
    # run the cell to populate the graph, globals
    await k.run([er := exec_req.get("'hello'; 123")])

    runner = Runner(
        cell_ids=set(k.graph.cells.keys()),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
    )
    run_result = await runner.run(er.cell_id)
    # last expression of cell is output
    assert run_result.output == 123


async def test_traceback_includes_lineno(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    # Raise an exception and test that the runner generates a traceback that
    # includes the line number where the exception was raised
    #
    # first run the cell to populate the graph
    await k.run(
        [
            er := exec_req.get(
                """
                x = 0
                raise ValueError
                """
            )
        ]
    )

    runner = Runner(
        cell_ids=set(k.graph.cells.keys()),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
    )
    with capture_stderr() as buffer:
        await runner.run(er.cell_id)
    assert "line 3" in buffer.getvalue()
