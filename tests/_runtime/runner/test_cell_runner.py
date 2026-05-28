# Copyright 2026 Marimo. All rights reserved.
import traceback

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.errors import MarimoSQLError
from marimo._runtime.capture import capture_stderr
from marimo._runtime.runner.cell_runner import Runner
from marimo._runtime.runner.hooks import NotebookCellHooks
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
        hooks=NotebookCellHooks(),
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
        hooks=NotebookCellHooks(),
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
        hooks=NotebookCellHooks(),
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
        hooks=NotebookCellHooks(),
    )

    with capture_stderr() as buffer:
        await runner.run(er.cell_id)

    stderr = buffer.getvalue()
    assert "Traceback (most recent call last):" not in stderr
    assert isinstance(runner.exceptions[er.cell_id], MarimoSQLError)


async def test_ui_element_update_skips_overridden_cells(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test that UI element updates skip cells whose defs are overridden."""
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
                # Embed with x overridden - the cell defining x should be skipped
                # on UI element updates
                embed_result = await app.embed(defs={"x": 100})
                slider_element = embed_result.defs["slider"]
                initial_result = embed_result.defs["result"]
                """
            ),
        ]
    )
    assert not k.errors
    # With x=100 overridden, result should be 200
    assert k.globals["initial_result"] == 200

    # Now update the slider - the cell defining x should NOT run
    # because x is overridden
    slider_element = k.globals["slider_element"]
    assert await k.set_ui_element_value(
        UpdateUIElementCommand.from_ids_and_values([(slider_element._id, 8)]),
        notify_frontend=False,
    )

    # After UI update, result should still be 200 because x is still overridden
    embed_result = k.globals["embed_result"]
    assert embed_result.defs["result"] == 200
    # x should still be the overridden value, not slider.value
    assert embed_result.defs["x"] == 100


async def test_converging_cell_stays_stopped_until_all_branches_trigger(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get_with_id("a", "mo.stop(True); a = 'A'"),
            exec_req.get("mo.stop(True); b = 'B'"),
            exec_req.get_with_id("res", "result = a + b"),
        ]
    )
    assert "a" not in k.globals
    assert "b" not in k.globals

    await k.run([exec_req.get_with_id("a", "a = 'A'")])

    assert "a" in k.globals
    assert "b" not in k.globals
    assert "result" not in k.globals
    assert k.graph.cells["res"].run_result_status == "cancelled"


async def test_sibling_cells_of_stopped_ancestor_both_cancelled(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get_with_id("stopper", "mo.stop(True); s = 1"),
            exec_req.get_with_id("trigger", "t = 1"),
            exec_req.get_with_id("s1", "x = s + t"),
            exec_req.get_with_id("s2", "y = s + t"),
        ]
    )
    assert "x" not in k.globals
    assert "y" not in k.globals

    await k.run([exec_req.get_with_id("trigger", "t = 2")])

    assert "x" not in k.globals
    assert "y" not in k.globals
    assert k.graph.cells["s1"].run_result_status == "cancelled"
    assert k.graph.cells["s2"].run_result_status == "cancelled"


async def test_converging_runs_when_all_branches_trigger(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get_with_id("a", "mo.stop(True); a = 'A'"),
            exec_req.get_with_id("b", "mo.stop(True); b = 'B'"),
            exec_req.get_with_id("res", "result = a + b"),
        ]
    )
    assert "a" not in k.globals
    assert "b" not in k.globals

    await k.run([exec_req.get_with_id("a", "a = 'A'")])
    await k.run([exec_req.get_with_id("b", "b = 'B'")])

    assert "a" in k.globals
    assert "b" in k.globals
    assert "result" in k.globals
    assert k.graph.cells["res"].run_result_status == "success"


# --- Surface 3: registered plugin Executor runs via Runner ------------------


async def test_runner_dispatches_to_registered_plugin_executor(
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A factory registered against `marimo.cell.executor` is the one
    the kernel `Runner` dispatches through."""
    from typing import Any

    from marimo._runtime.executor.evaluator import _EXECUTOR_REGISTRY

    recorded: list[str] = []
    sentinel_output = object()

    class _SentinelExecutor:
        name = "sentinel"

        def execute_cell(self, cell: Any, glbls: dict[str, Any]) -> object:
            del glbls
            recorded.append(cell.cell_id)
            return sentinel_output

        async def execute_cell_async(
            self, cell: Any, glbls: dict[str, Any]
        ) -> object:
            del glbls
            recorded.append(cell.cell_id)
            return sentinel_output

    def factory() -> _SentinelExecutor:
        return _SentinelExecutor()

    # Populate the kernel first (uses the real DefaultExecutor — the
    # registry isn't patched yet).
    k = execution_kernel
    await k.run([er := exec_req.get("'hello'; 123")])

    # Fully isolate the registry: replace both `_plugins` and
    # `names` so installed third-party entry points can't shadow the
    # sentinel. monkeypatch restores both on teardown.
    monkeypatch.setattr(_EXECUTOR_REGISTRY, "_plugins", {"sentinel": factory})
    monkeypatch.setattr(_EXECUTOR_REGISTRY, "names", lambda: ["sentinel"])

    runner = Runner(
        roots=set(k.graph.cells.keys()),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
        hooks=NotebookCellHooks(),
    )
    run_result = await runner.run(er.cell_id)

    assert recorded == [er.cell_id]
    assert run_result.output is sentinel_output


# --- Surface 4: Runner.interrupted flips on cancellation --------------------


async def test_runner_interrupted_flag_flips_on_sync_marimo_interrupt(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    """Sync cell body raising `MarimoInterrupt` (== `KeyboardInterrupt`)
    surfaces as a bare `MarimoInterrupt` in the run result and flips
    `runner.interrupted`."""
    k = execution_kernel
    await k.run([er := exec_req.get("raise KeyboardInterrupt")])

    runner = Runner(
        roots=set(k.graph.cells.keys()),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
        hooks=NotebookCellHooks(),
    )
    with capture_stderr():
        await runner.run(er.cell_id)

    assert runner.interrupted is True


async def test_runner_interrupted_flag_flips_on_async_cell_cancellation(
    execution_kernel: Kernel,
    exec_req: ExecReqProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An async cell cancelled mid-await flips `runner.interrupted`.

    A bare `asyncio.CancelledError` arriving in `RunResult.exception` is
    converted to `MarimoInterrupt` by the bare-`CancelledError` branch
    of `_finalize_run_result`, which `run()` recognises to flip the
    flag.

    Simulates the evaluator output directly (a bare `CancelledError` in
    the `RunResult`) so this test is independent of the executor's
    coroutine compilation.
    """
    import asyncio

    from marimo._runtime.runner.result import RunResult

    k = execution_kernel
    await k.run([er := exec_req.get("123")])

    runner = Runner(
        roots=set(k.graph.cells.keys()),
        graph=k.graph,
        glbls=k.globals,
        debugger=k.debugger,
        hooks=NotebookCellHooks(),
    )

    async def fake_evaluate(cell, glbls):  # type: ignore[no-untyped-def]
        del cell, glbls
        return RunResult(output=None, exception=asyncio.CancelledError())

    monkeypatch.setattr(
        runner._evaluator, "evaluate_interruptible", fake_evaluate
    )

    with capture_stderr():
        await runner.run(er.cell_id)

    assert runner.interrupted is True
