# Copyright 2026 Marimo. All rights reserved.
"""Tests for SerialTaskRunner."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from marimo._utils.serial_task_runner import SerialTaskRunner

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def runner() -> Generator[SerialTaskRunner, None, None]:
    r = SerialTaskRunner(thread_name_prefix="test")
    try:
        yield r
    finally:
        r.shutdown(wait=True)


class TestSyncPath:
    """Running without an event loop: work executes inline on the caller thread."""

    def test_submit_runs_work_inline_without_loop(
        self, runner: SerialTaskRunner
    ) -> None:
        called: list[int] = []
        runner.submit(lambda: called.append(1))
        assert called == [1]

    def test_submit_does_not_touch_executor_without_loop(
        self, runner: SerialTaskRunner
    ) -> None:
        """Inline path must not materialize the executor — that would
        leak a thread for run mode / IPC kernels."""
        runner.submit(lambda: None)
        assert "_executor" not in runner.__dict__

    def test_on_error_invoked_inline_without_loop(
        self, runner: SerialTaskRunner
    ) -> None:
        errors: list[Exception] = []

        def _fail() -> None:
            raise ValueError("boom")

        runner.submit(_fail, on_error=errors.append)
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)
        assert str(errors[0]) == "boom"

    def test_missing_on_error_is_swallowed(
        self, runner: SerialTaskRunner
    ) -> None:
        """Without an on_error handler, exceptions must still not
        propagate out of submit()."""
        runner.submit(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        # Reached here — no exception raised

    def test_failing_on_error_is_swallowed(
        self, runner: SerialTaskRunner
    ) -> None:
        def _fail() -> None:
            raise ValueError("original")

        def _bad_handler(_err: Exception) -> None:
            raise RuntimeError("handler also fails")

        runner.submit(_fail, on_error=_bad_handler)
        # Reached here — outer exception swallowed


class TestAsyncPath:
    """Running inside an event loop: work executes on the worker thread."""

    async def test_submit_offloads_to_executor_thread(
        self, runner: SerialTaskRunner
    ) -> None:
        caller_thread = threading.current_thread()
        work_thread: list[threading.Thread] = []

        def _work() -> None:
            work_thread.append(threading.current_thread())

        runner.submit(_work)
        await runner.drain()

        assert len(work_thread) == 1
        assert work_thread[0] is not caller_thread
        assert work_thread[0].name.startswith("test")

    async def test_fifo_ordering_under_concurrent_submits(
        self,
        runner: SerialTaskRunner,
    ) -> None:
        """A slow earlier task must finish before a faster later task."""
        completion_order: list[int] = []

        def _make_work(idx: int, delay: float) -> Any:
            def _work() -> None:
                time.sleep(delay)
                completion_order.append(idx)

            return _work

        runner.submit(_make_work(0, 0.05))
        runner.submit(_make_work(1, 0.0))
        runner.submit(_make_work(2, 0.0))
        await runner.drain()

        assert completion_order == [0, 1, 2]

    async def test_on_error_runs_on_event_loop_thread(
        self, runner: SerialTaskRunner
    ) -> None:
        """``on_error`` must be posted back to the loop via
        ``call_soon_threadsafe`` — many callers need to touch asyncio
        primitives that are not thread-safe."""
        loop_thread = threading.current_thread()
        handler_thread: list[threading.Thread] = []

        def _fail() -> None:
            raise ValueError("boom")

        def _on_error(_err: Exception) -> None:
            handler_thread.append(threading.current_thread())

        runner.submit(_fail, on_error=_on_error)
        await runner.drain()
        # on_error is scheduled via call_soon_threadsafe; yield once so
        # the loop picks it up.
        await asyncio.sleep(0)

        assert len(handler_thread) == 1
        assert handler_thread[0] is loop_thread

    async def test_drain_with_no_pending_is_noop(
        self, runner: SerialTaskRunner
    ) -> None:
        await runner.drain()  # should not raise or hang

    async def test_pending_list_prunes_done_futures(
        self, runner: SerialTaskRunner
    ) -> None:
        runner.submit(lambda: None)
        await runner.drain()
        # Drain clears the list
        assert runner.pending == []

        # New submit after drain — list rebuilds cleanly
        runner.submit(lambda: None)
        await runner.drain()
        assert runner.pending == []

    async def test_failed_task_does_not_block_drain(
        self, runner: SerialTaskRunner
    ) -> None:
        runner.submit(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        runner.submit(lambda: None)
        # drain() uses return_exceptions=True, so the first task's
        # failure shouldn't abort the second.
        await runner.drain()


class TestShutdown:
    """Lifecycle and executor cleanup."""

    def test_shutdown_before_any_submit_is_noop(self) -> None:
        runner = SerialTaskRunner(thread_name_prefix="shutdown-only")
        runner.shutdown()
        # No executor ever materialized
        assert "_executor" not in runner.__dict__

    def test_shutdown_is_idempotent(self) -> None:
        runner = SerialTaskRunner(thread_name_prefix="idempotent")
        runner.submit(lambda: None)
        runner.shutdown(wait=True)
        runner.shutdown(wait=True)  # should not raise

    async def test_shutdown_wait_true_blocks_until_done(self) -> None:
        runner = SerialTaskRunner(thread_name_prefix="blocking")
        completed = threading.Event()

        def _slow_work() -> None:
            time.sleep(0.05)
            completed.set()

        runner.submit(_slow_work)
        await runner.drain()
        runner.shutdown(wait=True)
        assert completed.is_set()

    def test_submit_after_shutdown_sync_is_noop(self) -> None:
        """Regression: a stray submit() after shutdown must not
        re-materialize the ``cached_property`` executor — otherwise
        session teardown can race with ``QueueDistributor.stop()`` and
        spin up a brand-new worker thread on the way out."""
        runner = SerialTaskRunner(thread_name_prefix="closed-sync")
        runner.shutdown()

        called: list[int] = []
        runner.submit(lambda: called.append(1))

        assert called == []
        assert "_executor" not in runner.__dict__

    async def test_submit_after_shutdown_async_is_noop(self) -> None:
        """Same regression guard, but from the event-loop code path."""
        runner = SerialTaskRunner(thread_name_prefix="closed-async")
        # Materialize and immediately shut down.
        runner.submit(lambda: None)
        await runner.drain()
        runner.shutdown(wait=True)

        called: list[int] = []
        runner.submit(lambda: called.append(1))
        # Nothing was scheduled, so drain has nothing to await.
        await runner.drain()

        assert called == []
        assert "_executor" not in runner.__dict__
        assert runner.pending == []
