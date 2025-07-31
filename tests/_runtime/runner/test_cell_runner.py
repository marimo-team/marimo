# Copyright 2024 Marimo. All rights reserved.
import traceback

from marimo._runtime.capture import capture_stderr
from marimo._runtime.runner.cell_runner import Runner
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_cell_output(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    # run the cell to populate the graph, globals
    await k.run([er := exec_req.get("'hello'; 123")])

    runner = Runner(
        roots=set(k.graph.cells.keys()),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
    )
    run_result = await runner.run(er.cell_id)
    # last expression of cell is output
    assert run_result.output == 123
    assert k.debugger._last_traceback is None


async def test_traceback_includes_lineno(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    # Raise an exception and test that the runner generates a traceback that
    # includes the line number where the exception was raised
    #
    # first run the cell to populate the graph
    await k.run(
        [
            er := exec_req.get_with_id(
                "1",
                """
                x = 0
                raise ValueError
                """,
            )
        ]
    )

    runner = Runner(
        roots=set(k.graph.cells.keys()),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
    )
    with capture_stderr() as buffer:
        await runner.run(er.cell_id)
    assert "line 3" in buffer.getvalue()
    assert k.debugger._last_traceback == k.debugger._last_tracebacks["1"]
    assert k.debugger._last_traceback is not None
    assert "line 3" in "\n".join(
        traceback.format_tb(k.debugger._last_traceback)
    )


async def test_base_exception_caught(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    # Raise an exception and test that the runner generates a traceback that
    # includes the line number where the exception was raised
    #
    # Make sure BaseException is caught
    #
    # first run the cell to populate the graph
    await k.run(
        [
            er := exec_req.get_with_id(
                "1",
                """
                x = 0
                raise BaseException
                """,
            )
        ]
    )

    runner = Runner(
        roots=set(k.graph.cells.keys()),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
    )
    with capture_stderr() as buffer:
        await runner.run(er.cell_id)
    assert "line 3" in buffer.getvalue()
    assert k.debugger._last_traceback == k.debugger._last_tracebacks["1"]
    assert k.debugger._last_traceback is not None
    assert "line 3" in "\n".join(
        traceback.format_tb(k.debugger._last_traceback)
    )
