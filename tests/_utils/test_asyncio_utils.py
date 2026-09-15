from __future__ import annotations

import asyncio
import sys

import pytest

from marimo._utils.asyncio_utils import (
    cancel_and_wait,
    fire_and_forget,
    run_on_subprocess_capable_loop,
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


def test_run_on_subprocess_capable_loop_returns_and_cleans_up() -> None:
    loop: asyncio.AbstractEventLoop | None = None
    pending: asyncio.Task[None] | None = None

    async def main() -> int:
        nonlocal loop, pending
        loop = asyncio.get_running_loop()
        pending = asyncio.create_task(asyncio.sleep(3600))
        await asyncio.sleep(0)
        return 42

    assert run_on_subprocess_capable_loop(main()) == 42
    assert pending is not None
    assert pending.cancelled()
    assert loop is not None
    assert loop.is_closed()


def test_run_on_subprocess_capable_loop_propagates_exception() -> None:
    async def main() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_on_subprocess_capable_loop(main())


def test_run_on_subprocess_capable_loop_rejects_running_loop() -> None:
    async def inner() -> None:
        pass

    async def outer() -> None:
        coro = inner()
        try:
            with pytest.raises(RuntimeError):
                run_on_subprocess_capable_loop(coro)
        finally:
            coro.close()

    asyncio.run(outer())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only loop")
def test_run_on_subprocess_capable_loop_spawns_under_selector_policy() -> None:
    original = asyncio.get_event_loop_policy()
    selector_policy = asyncio.WindowsSelectorEventLoopPolicy()
    asyncio.set_event_loop_policy(selector_policy)

    async def main() -> tuple[bool, int | None, bytes]:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "print('ok')",
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        is_proactor = isinstance(
            asyncio.get_running_loop(), asyncio.ProactorEventLoop
        )
        return is_proactor, proc.returncode, stdout

    try:
        is_proactor, returncode, stdout = run_on_subprocess_capable_loop(
            main()
        )
        assert asyncio.get_event_loop_policy() is selector_policy
    finally:
        asyncio.set_event_loop_policy(original)

    assert is_proactor
    assert returncode == 0
    assert stdout.decode().strip() == "ok"
