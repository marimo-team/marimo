from __future__ import annotations

import asyncio
import threading

import pytest

from marimo._utils.asyncio_utils import (
    cancel_and_wait,
    fire_and_forget,
    run_coroutine_blocking,
    supervised_task,
)


async def test_supervised_task_runs_and_returns_result() -> None:
    async def work() -> int:
        await asyncio.sleep(0)
        return 42

    task = supervised_task(work(), name="work")
    assert await task == 42


async def test_supervised_task_logs_unhandled_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from marimo._utils import asyncio_utils

    seen: list[str] = []

    def fake_error(msg: str, *args: object, **kwargs: object) -> None:
        del kwargs
        seen.append(msg % args if args else msg)

    monkeypatch.setattr(asyncio_utils.LOGGER, "error", fake_error)

    async def boom() -> None:
        raise ValueError("nope")

    task = supervised_task(boom(), name="boom")
    with pytest.raises(ValueError):
        await task
    await asyncio.sleep(0)
    assert any("boom" in msg for msg in seen)


async def test_supervised_task_registry_lifecycle() -> None:
    registry: set[asyncio.Task[object]] = set()

    async def work() -> None:
        await asyncio.sleep(0)

    task = supervised_task(work(), name="work", registry=registry)
    assert task in registry
    await task
    await asyncio.sleep(0)
    assert task not in registry


async def test_supervised_task_custom_on_exception() -> None:
    seen: list[BaseException] = []

    async def boom() -> None:
        raise RuntimeError("x")

    task = supervised_task(
        boom(), name="boom", on_exception=lambda e: seen.append(e)
    )
    with pytest.raises(RuntimeError):
        await task
    await asyncio.sleep(0)
    assert len(seen) == 1
    assert isinstance(seen[0], RuntimeError)


async def test_fire_and_forget_with_running_loop() -> None:
    started = asyncio.Event()
    finished = asyncio.Event()

    async def work() -> None:
        started.set()
        await asyncio.sleep(0)
        finished.set()

    task = fire_and_forget(work(), name="ff")
    assert task is not None
    await started.wait()
    await finished.wait()


def test_fire_and_forget_without_running_loop_runs_synchronously() -> None:
    ran = False

    async def work() -> None:
        nonlocal ran
        ran = True

    result = fire_and_forget(work(), name="ff")
    assert result is None
    assert ran


async def test_cancel_and_wait_swallows_cancelled_error() -> None:
    async def sleeper() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(sleeper())
    await asyncio.sleep(0)
    await cancel_and_wait(task)
    assert task.cancelled()


async def test_cancel_and_wait_preserves_exception_on_done_task() -> None:
    # If the task already failed before we tried to cancel, the
    # exception is marked retrieved (no "Task exception was never
    # retrieved" warning) but stays queryable.
    async def boom() -> None:
        raise ValueError("boom")

    task = asyncio.create_task(boom())
    await asyncio.sleep(0)
    await cancel_and_wait(task)
    assert isinstance(task.exception(), ValueError)


async def test_cancel_and_wait_done_task_is_noop() -> None:
    async def fast() -> int:
        return 1

    task = asyncio.create_task(fast())
    await task
    await cancel_and_wait(task)


def test_run_coroutine_blocking_without_running_loop() -> None:
    async def work() -> int:
        await asyncio.sleep(0)
        return 42

    assert run_coroutine_blocking(work()) == 42


def test_run_coroutine_blocking_without_running_loop_stays_on_thread() -> None:
    caller = threading.get_ident()

    async def work() -> int:
        return threading.get_ident()

    # No loop is running, so there is no reason to pay for a worker thread.
    assert run_coroutine_blocking(work()) == caller


async def test_run_coroutine_blocking_with_running_loop() -> None:
    async def work() -> int:
        await asyncio.sleep(0)
        return 42

    # `asyncio.run` would raise here; the coroutine is offloaded instead.
    assert run_coroutine_blocking(work()) == 42


async def test_run_coroutine_blocking_with_running_loop_uses_worker() -> None:
    caller = threading.get_ident()

    async def work() -> int:
        return threading.get_ident()

    assert run_coroutine_blocking(work()) != caller


async def test_run_coroutine_blocking_propagates_exception() -> None:
    async def boom() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_coroutine_blocking(boom())


async def test_run_coroutine_blocking_nests() -> None:
    async def inner() -> int:
        await asyncio.sleep(0)
        return 2

    async def outer() -> int:
        # Each level has its own running loop, so each offloads again.
        return 1 + run_coroutine_blocking(inner())

    assert run_coroutine_blocking(outer()) == 3
