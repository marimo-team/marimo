# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import signal
import sys
import threading
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.streams import ThreadSafeStream
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import ExecutionContext
from marimo._runtime.executor.evaluator import Evaluator
from marimo._runtime.handlers import construct_interrupt_handler
from marimo._runtime.runtime import MarimoInterrupt

if TYPE_CHECKING:
    from marimo._runtime.runner.result import RunResult
    from marimo._runtime.runtime import Kernel
    from tests.conftest import ExecReqProvider, MockedKernel

HAS_DUCKDB = DependencyManager.duckdb.has()


def _kernel_context_mock(exec_ctx: ExecutionContext) -> MagicMock:
    """Mock that satisfies the handler's `isinstance(KernelRuntimeContext)`
    check; `active_scheduler=None` selects the sync raise path."""
    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = exec_ctx
    ctx.active_scheduler = None
    return ctx


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_interrupt_handler_called_when_connection_present():
    """Test that duckdb.interrupt() is called when a connection is present."""
    import duckdb

    # Create a mock connection that we can spy on
    mock_conn = MagicMock(spec=duckdb.DuckDBPyConnection)

    # Create an execution context with a duckdb connection
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)

    with patch(
        "marimo._runtime.handlers.safe_get_context"
    ) as mock_safe_get_context:
        mock_safe_get_context.return_value = _kernel_context_mock(exec_ctx)

        with exec_ctx.with_connection(mock_conn):
            interrupt_handler = construct_interrupt_handler()

            # Trigger the interrupt handler
            with pytest.raises(MarimoInterrupt):
                interrupt_handler(signal.SIGINT, None)

            # Verify duckdb connection's interrupt was called
            mock_conn.interrupt.assert_called_once()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_interrupt_handler_no_error_when_connection_none():
    """Test that no error occurs when connection is None."""
    # Create an execution context without a connection
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)
    exec_ctx.duckdb_connection = None

    # Mock the context to return our execution context
    with patch(
        "marimo._runtime.handlers.safe_get_context"
    ) as mock_safe_get_context:
        mock_context = _kernel_context_mock(exec_ctx)
        mock_safe_get_context.return_value = mock_context

        interrupt_handler = construct_interrupt_handler()

        # Should not raise error from duckdb interrupt (only MarimoInterrupt)
        with pytest.raises(MarimoInterrupt):
            interrupt_handler(signal.SIGINT, None)


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_interrupt_handler_exception_handling():
    """Test that exceptions during interrupt() don't crash the kernel."""
    import duckdb

    # Create a mock connection that raises an exception
    mock_conn = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_conn.interrupt.side_effect = RuntimeError("Mock error")

    # Create an execution context with a duckdb connection
    exec_ctx = ExecutionContext(cell_id="cell_id", setting_element_value=False)

    # Mock the context to return our execution context
    with patch(
        "marimo._runtime.handlers.safe_get_context"
    ) as mock_safe_get_context:
        mock_context = _kernel_context_mock(exec_ctx)
        mock_safe_get_context.return_value = mock_context

        # Make interrupt() raise an exception
        with exec_ctx.with_connection(mock_conn):
            interrupt_handler = construct_interrupt_handler()

            # Should raise MarimoInterrupt, not RuntimeError
            # The RuntimeError should be caught and logged
            with pytest.raises(MarimoInterrupt):
                interrupt_handler(signal.SIGINT, None)

            # Verify interrupt was attempted
            mock_conn.interrupt.assert_called_once()


def test_sigint_between_cells_cancels_queue_and_raises() -> None:
    """SIGINT landing between two cells (scheduler still running its
    queue, no cell installed in `execution_context`) must halt the
    queue and raise `MarimoInterrupt`. Regression for the P2 where the
    handler returned early on `execution_context is None` before
    consulting `active_scheduler`."""
    sched = MagicMock()
    sched.has_active_tasks.return_value = False

    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = None
    ctx.active_scheduler = sched

    with patch("marimo._runtime.handlers.safe_get_context", return_value=ctx):
        interrupt_handler = construct_interrupt_handler()
        with pytest.raises(MarimoInterrupt):
            interrupt_handler(signal.SIGINT, None)

    sched.cancel_all.assert_called_once()


async def test_sigint_with_suspended_async_task_cancels_without_raising() -> (
    None
):
    """When an async cell is in flight but not running (the scheduler does
    not own the current task), the handler must call `cancel_all` and
    return — raising from a signal handler would escape into asyncio
    internals and surface as an internal-error empty RunResult."""
    sched = MagicMock()
    sched.has_active_tasks.return_value = True
    sched.interrupt_current_task.return_value = None

    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = None
    ctx.active_scheduler = sched

    with patch("marimo._runtime.handlers.safe_get_context", return_value=ctx):
        interrupt_handler = construct_interrupt_handler()
        # No exception raised.
        interrupt_handler(signal.SIGINT, None)

    sched.cancel_all.assert_called_once()


def test_sigint_with_no_scheduler_and_no_cell_is_noop() -> None:
    """No scheduler installed and no cell in flight — the handler must
    return silently without raising or calling broadcast."""
    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = None
    ctx.active_scheduler = None

    with patch("marimo._runtime.handlers.safe_get_context", return_value=ctx):
        interrupt_handler = construct_interrupt_handler()
        # No exception raised.
        interrupt_handler(signal.SIGINT, None)


def test_ignore_console_ctrl_c_keeps_interrupt_main_working() -> None:
    """`interrupt_main()` (the deliberate interrupt path) must still fire
    the SIGINT handler after `ignore_console_ctrl_c()`. Runs in a
    subprocess to leave the test runner's console handling untouched."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        import signal, sys, threading, _thread
        from marimo._runtime.win32_interrupt_handler import (
            ignore_console_ctrl_c,
        )

        fired = threading.Event()
        signal.signal(signal.SIGINT, lambda *args: fired.set())
        ignore_console_ctrl_c()
        threading.Timer(0.1, _thread.interrupt_main).start()
        fired.wait(5)
        sys.exit(0 if fired.is_set() else 1)
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], timeout=30, capture_output=True
    )
    assert completed.returncode == 0, completed.stderr.decode()


def _active_scheduler_context() -> MagicMock:
    sched = MagicMock()
    sched.has_active_tasks.return_value = False
    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.execution_context = None
    ctx.active_scheduler = sched
    return ctx


def test_handler_does_not_broadcast() -> None:
    """The handler runs between arbitrary bytecodes and can run nested.
    It must not write to the kernel stream, because the stream write
    takes a non-reentrant lock."""
    ctx = _active_scheduler_context()
    ctx.stream = MagicMock()

    with (
        patch("marimo._runtime.handlers.safe_get_context", return_value=ctx),
        patch(
            "marimo._messaging.notification_utils.get_context",
            return_value=ctx,
        ),
    ):
        interrupt_handler = construct_interrupt_handler()
        with pytest.raises(MarimoInterrupt):
            interrupt_handler(signal.SIGINT, None)

    ctx.stream.write.assert_not_called()


def test_handler_finishes_while_stream_lock_is_held() -> None:
    """A second SIGINT can arrive while the kernel holds `stream_lock`.
    The handler must still finish, so the kernel main thread cannot
    deadlock inside the signal handler."""
    stream = ThreadSafeStream(
        pipe=MagicMock(), input_queue=MagicMock(), redirect_console=False
    )
    ctx = _active_scheduler_context()
    ctx.stream = stream
    outcome: list[str] = []

    def run_handler() -> None:
        with (
            patch(
                "marimo._runtime.handlers.safe_get_context",
                return_value=ctx,
            ),
            patch(
                "marimo._messaging.notification_utils.get_context",
                return_value=ctx,
            ),
        ):
            interrupt_handler = construct_interrupt_handler()
            try:
                interrupt_handler(signal.SIGINT, None)
            except MarimoInterrupt:
                outcome.append("raised")

    worker = threading.Thread(target=run_handler, daemon=True)
    with stream.stream_lock:
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive(), "handler blocked on stream_lock"
    assert outcome == ["raised"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize(
    "body",
    [
        # SIGINT during blocking code after, then before, the only `await`.
        "await asyncio.sleep(0)\nos.kill(os.getpid(), signal.SIGINT)\n"
        + "time.sleep(5)",
        "os.kill(os.getpid(), signal.SIGINT)\ntime.sleep(5)\n"
        + "await asyncio.sleep(0)",
    ],
    ids=["await-then-block", "block-then-await"],
)
async def test_sigint_interrupts_async_cell_running_blocking_code(
    k: Kernel, exec_req: ExecReqProvider, body: str
) -> None:
    previous = signal.signal(signal.SIGINT, construct_interrupt_handler())
    try:
        await k.run(
            [
                cell := exec_req.get(
                    f"import asyncio, os, signal, time\n{body}\nz = 1"
                ),
                child := exec_req.get("w = z + 1"),
            ]
        )
    finally:
        signal.signal(signal.SIGINT, previous)

    assert "z" not in k.globals
    assert k.graph.cells[cell.cell_id].run_result_status == "interrupted"
    assert k.graph.cells[child.cell_id].run_result_status == "cancelled"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize(
    "spawn",
    [
        "await asyncio.gather(work())",
        "await asyncio.create_task(work())",
        # The child's cancellation is returned as a value, so only the
        # cell's own cancellation can stop the cell.
        "await asyncio.gather(work(), return_exceptions=True)",
        # A task group ignores a cancelled child.
        "async with asyncio.TaskGroup() as tg:\n    tg.create_task(work())",
        # The cell is suspended on something unrelated to the child.
        "asyncio.create_task(work())\nawait asyncio.sleep(10)",
    ],
    ids=[
        "gather",
        "create_task",
        "gather-return-exceptions",
        "task-group",
        "background-child",
    ],
)
async def test_sigint_interrupts_blocking_child_coroutine(
    k: Kernel, exec_req: ExecReqProvider, spawn: str
) -> None:
    previous = signal.signal(signal.SIGINT, construct_interrupt_handler())
    try:
        await k.run(
            [
                exec_req.get("log = []"),
                cell := exec_req.get(
                    "import asyncio, os, signal, time\n"
                    "async def work():\n"
                    "    log.append('child started')\n"
                    "    try:\n"
                    "        os.kill(os.getpid(), signal.SIGINT)\n"
                    "        time.sleep(5)\n"
                    "        log.append('continued')\n"
                    "    finally:\n"
                    "        await asyncio.sleep(0)\n"
                    "        log.append('cleanup finished')\n"
                    f"{spawn}\n"
                    "z = 1"
                ),
                dependent := exec_req.get("w = z + 1"),
            ]
        )
    finally:
        signal.signal(signal.SIGINT, previous)

    # The child is interrupted before "continued". Its cleanup after the
    # `await` runs only when the cell's cancellation does not reach it.
    assert k.globals["log"][0] == "child started"
    assert "continued" not in k.globals["log"]
    assert "z" not in k.globals
    assert k.graph.cells[cell.cell_id].run_result_status == "interrupted"
    assert k.graph.cells[dependent.cell_id].run_result_status == "cancelled"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.parametrize("kernel", ["k", "strict_kernel"])
def test_sigint_outside_async_cell_body_halts_run_and_keeps_kernel(
    request: pytest.FixtureRequest, kernel: str, exec_req: ExecReqProvider
) -> None:
    k: Kernel = request.getfixturevalue(kernel)
    asyncio.run(k.run([exec_req.get("sentinel = 42")]))

    teardown_chain = Evaluator._teardown_chain

    def interrupt_then_teardown(
        self: Evaluator, *args: Any, **kwargs: Any
    ) -> RunResult:
        # The handler runs in the cell's task after the body finished,
        # before the lifecycles (strict mode's globals restore) tear down.
        os.kill(os.getpid(), signal.SIGINT)
        return teardown_chain(self, *args, **kwargs)

    previous = signal.signal(signal.SIGINT, construct_interrupt_handler())
    try:
        with patch.object(
            Evaluator, "_teardown_chain", interrupt_then_teardown
        ):
            asyncio.run(
                k.run(
                    [
                        cell := exec_req.get(
                            "import asyncio\nawait asyncio.sleep(0)\nz = 1"
                        ),
                        exec_req.get("w = z + 1"),
                    ]
                )
            )
    except KeyboardInterrupt:
        pytest.fail("SIGINT escaped the cell's task and stopped the loop")
    finally:
        signal.signal(signal.SIGINT, previous)

    assert "w" not in k.globals
    asyncio.run(k.run([exec_req.get("y = sentinel + 1")]))
    assert k.globals["y"] == 43
    # The body finished before the interrupt.
    assert k.graph.cells[cell.cell_id].run_result_status == "success"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
async def test_sigint_in_async_cell_lets_awaited_cleanup_finish(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    previous = signal.signal(signal.SIGINT, construct_interrupt_handler())
    try:
        await k.run(
            [
                exec_req.get("log = []"),
                cell := exec_req.get(
                    "import asyncio, os, signal, time\n"
                    "try:\n"
                    "    os.kill(os.getpid(), signal.SIGINT)\n"
                    "    time.sleep(5)\n"
                    "finally:\n"
                    "    await asyncio.sleep(0)\n"
                    "    log.append('cleanup finished')"
                ),
            ]
        )
    finally:
        signal.signal(signal.SIGINT, previous)

    assert k.globals["log"] == ["cleanup finished"]
    assert k.graph.cells[cell.cell_id].run_result_status == "interrupted"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
async def test_sigint_in_one_child_stops_its_siblings(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    previous = signal.signal(signal.SIGINT, construct_interrupt_handler())
    try:
        await k.run(
            [
                cell := exec_req.get(
                    "import asyncio, os, signal, time\n"
                    "steps = []\n"
                    "async def work(i):\n"
                    "    for step in range(5):\n"
                    "        if i == 0 and step == 0:\n"
                    "            os.kill(os.getpid(), signal.SIGINT)\n"
                    "        time.sleep(0.01)\n"
                    "        steps.append((i, step))\n"
                    "        await asyncio.sleep(0)\n"
                    "tasks = [asyncio.create_task(work(i)) for i in range(3)]\n"
                    "await asyncio.gather(*tasks)\n"
                    "z = 1"
                ),
            ]
        )
    finally:
        signal.signal(signal.SIGINT, previous)

    # Let the cancelled siblings take their final turn.
    for _ in range(5):
        await asyncio.sleep(0)
    siblings = k.globals["tasks"][1:]
    assert all(task.cancelled() for task in siblings)
    # Each sibling ran at most one step before its cancellation arrived.
    assert len(k.globals["steps"]) <= len(siblings)
    assert "z" not in k.globals
    assert k.graph.cells[cell.cell_id].run_result_status == "interrupted"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
async def test_sigint_in_a_leftover_task_interrupts_the_running_cell(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """A task that outlives the cell that started it keeps the body marker,
    but the marker is stale, so the interrupt stops the cell that is
    running now."""
    previous = signal.signal(signal.SIGINT, construct_interrupt_handler())
    try:
        await k.run(
            [
                earlier := exec_req.get(
                    "import asyncio, os, signal, time\n"
                    "await asyncio.sleep(0)\n"
                    "async def spin():\n"
                    "    await asyncio.sleep(0.05)\n"
                    "    os.kill(os.getpid(), signal.SIGINT)\n"
                    "leftover = asyncio.create_task(spin())"
                ),
                running := exec_req.get(
                    "await asyncio.sleep(5)\nfinished = True"
                ),
            ]
        )
    finally:
        signal.signal(signal.SIGINT, previous)

    assert k.graph.cells[earlier.cell_id].run_result_status == "success"
    assert k.graph.cells[running.cell_id].run_result_status == "interrupted"
    assert "finished" not in k.globals


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
async def test_sigint_in_child_prints_no_traceback(
    mocked_kernel: MockedKernel, exec_req: ExecReqProvider
) -> None:
    k = mocked_kernel.k
    previous = signal.signal(signal.SIGINT, construct_interrupt_handler())
    try:
        await k.run(
            [
                cell := exec_req.get(
                    "import asyncio, os, signal, time\n"
                    "async def work():\n"
                    "    os.kill(os.getpid(), signal.SIGINT)\n"
                    "    time.sleep(1)\n"
                    "await asyncio.gather(work())"
                ),
            ]
        )
    finally:
        signal.signal(signal.SIGINT, previous)

    assert k.graph.cells[cell.cell_id].run_result_status == "interrupted"
    console = "".join(str(m) for m in mocked_kernel.stderr.messages)
    assert "Traceback" not in console
