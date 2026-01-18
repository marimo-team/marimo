# Copyright 2026 Marimo. All rights reserved.
import traceback

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.errors import MarimoSQLError
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


@pytest.mark.skipif(
    not DependencyManager.sqlglot.has(), reason="SQLGlot not installed"
)
async def test_sql_parse_error_suppresses_python_traceback(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    # first run the cell to populate the graph
    await k.run(
        [
            er := exec_req.get_with_id(
                "sql-1",
                """
from sqlglot.errors import ParseError
raise ParseError("malformed SQL")
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

    stderr = buffer.getvalue()
    assert "Traceback (most recent call last):" not in stderr
    assert isinstance(runner.exceptions[er.cell_id], MarimoSQLError)


async def test_ui_element_update_skips_overriden_cells(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that UI element updates skip cells whose defs are overriden."""
    from marimo._runtime.commands import UpdateUIElementCommand

    k = execution_kernel
    await k.run(
        [
            exec_req.get(
                """
                from marimo import App
                import marimo as mo

                app = App()

                @app.cell
                def _():
                    import marimo as mo
                    # Use a counter to track how many times this cell runs
                    slider = mo.ui.slider(0, 10, value=5)
                    return (slider,)

                @app.cell
                def _(slider):
                    # This cell defines x based on the slider
                    x = slider.value
                    return (x,)

                @app.cell
                def _(x):
                    # This cell uses x
                    result = x * 2
                    return (result,)
                """
            ),
            exec_req.get(
                """
                # Embed with x overriden - the cell defining x should be skipped
                # on UI element updates
                embed_result = await app.embed(defs={"x": 100})
                slider_element = embed_result.defs["slider"]
                initial_result = embed_result.defs["result"]
                """
            ),
        ]
    )
    assert not k.errors
    # With x=100 overriden, result should be 200
    assert k.globals["initial_result"] == 200

    # Now update the slider - the cell defining x should NOT run
    # because x is overriden
    slider_element = k.globals["slider_element"]
    assert await k.set_ui_element_value(
        UpdateUIElementCommand.from_ids_and_values([(slider_element._id, 8)])
    )

    # After UI update, result should still be 200 because x is still overriden
    embed_result = k.globals["embed_result"]
    assert embed_result.defs["result"] == 200
    # x should still be the overriden value, not slider.value
    assert embed_result.defs["x"] == 100
