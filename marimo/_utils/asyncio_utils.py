# Copyright 2026 Marimo. All rights reserved.
"""Small in-tree asyncio helpers.

- `supervised_task` / `fire_and_forget`: create a task that won't be
  garbage-collected mid-flight and whose non-cancellation exceptions
  are always logged on completion (intended for fire-and-forget work
  where the loop's default handler would otherwise swallow them).
- `cancel_and_wait`: the `task.cancel(); await task` /
  `except CancelledError` dance, in one place.
- `run_on_subprocess_capable_loop`: `asyncio.run` on a loop that can spawn
  subprocesses, even when marimo installed the Windows selector policy.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from typing import TYPE_CHECKING, Any, TypeVar

from marimo import _loggers

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")

# Strong refs for fire_and_forget tasks; the loop only holds weak refs,
# so without this the task can be GC'd mid-flight.
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


def _log_task_exception(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        LOGGER.error(
            "Exception in background task %r",
            task.get_name(),
            exc_info=exc,
        )


def supervised_task(
    coro: Coroutine[Any, Any, T],
    *,
    name: str,
    registry: set[asyncio.Task[Any]] | None = None,
    on_exception: Callable[[BaseException], None] | None = None,
) -> asyncio.Task[T]:
    """Schedule `coro` with a strong reference and exception logging.

    Intended for fire-and-forget or shutdown-cancelled background tasks.
    A done-callback logs every non-cancellation exception at error level.

    **Do not use this for tasks you plan to `await`.** The done-callback
    logs the exception even if the awaiter also handles it, producing
    duplicate logs. For awaited tasks, prefer plain `asyncio.create_task`
    — or pass `on_exception=lambda _: None` to opt out of logging while
    still benefiting from the strong-ref `registry` tracking.

    Args:
        coro: The coroutine to schedule.
        name: Task name (shows up in logs and `asyncio.all_tasks()`).
        registry: Optional set the task is added to and removed from on
            completion. Pass one for lifespan-scoped tracking.
        on_exception: Optional callback that replaces the default error
            log. Receives the exception; runs for non-cancellation
            failures only.

    Must be called from within a running event loop.
    """
    task = asyncio.create_task(coro, name=name)

    if registry is not None:
        registry.add(task)
        task.add_done_callback(registry.discard)

    if on_exception is not None:

        def _handle(t: asyncio.Task[Any]) -> None:
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                try:
                    on_exception(exc)
                except Exception:
                    LOGGER.exception(
                        "on_exception handler for task %r raised",
                        t.get_name(),
                    )

        task.add_done_callback(_handle)
    else:
        task.add_done_callback(_log_task_exception)

    return task


def initialize_asyncio() -> None:
    """Platform-specific initialization of asyncio.

    Sessions use the `add_reader()` API, which is only available in
    the SelectorEventLoop policy; Windows defaults to the Proactor.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def fire_and_forget(
    coro: Coroutine[Any, Any, Any], *, name: str
) -> asyncio.Task[Any] | None:
    """Schedule `coro` on the running loop; caller will not await it.

    Falls back to a synchronous `asyncio.run` (returning `None`) when
    no loop is running. The platform policy is initialized first so the
    fallback loop matches the selector-loop policy marimo relies on
    elsewhere (required on Windows for `add_reader`).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        initialize_asyncio()
        asyncio.run(coro)
        return None
    return supervised_task(coro, name=name, registry=_BACKGROUND_TASKS)


def run_on_subprocess_capable_loop(coro: Coroutine[Any, Any, T]) -> T:
    """Run `coro` to completion on a fresh loop that supports subprocesses.

    Equivalent to `asyncio.run(coro)`, except on Windows, where the loop is
    always a `ProactorEventLoop`. marimo installs the
    `WindowsSelectorEventLoopPolicy` process-wide because the server needs
    `add_reader()`, but selector loops on Windows cannot spawn subprocesses,
    so user code calling `asyncio.create_subprocess_exec` would fail.

    The global policy is never mutated: other threads (e.g. the server)
    create event loops concurrently and would race with the change.
    """
    if sys.platform != "win32":
        return asyncio.run(coro)
    if asyncio._get_running_loop() is not None:
        raise RuntimeError(
            "asyncio.run() cannot be called from a running event loop"
        )
    if sys.version_info >= (3, 12):
        return asyncio.run(coro, loop_factory=asyncio.ProactorEventLoop)
    if sys.version_info >= (3, 11):
        with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
            return runner.run(coro)
    return _run_with_loop_factory_py310(coro, asyncio.ProactorEventLoop)


def _run_with_loop_factory_py310(
    coro: Coroutine[Any, Any, T],
    loop_factory: Callable[[], asyncio.AbstractEventLoop],
) -> T:
    # Mirrors CPython 3.10's `asyncio.run`, which has no `loop_factory`.
    loop = loop_factory()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            to_cancel = asyncio.all_tasks(loop)
            for task in to_cancel:
                task.cancel()
            loop.run_until_complete(
                asyncio.gather(*to_cancel, return_exceptions=True)
            )
            for task in to_cancel:
                if not task.cancelled() and task.exception() is not None:
                    loop.call_exception_handler(
                        {
                            "message": "unhandled exception during "
                            "asyncio.run() shutdown",
                            "exception": task.exception(),
                            "task": task,
                        }
                    )
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


async def cancel_and_wait(task: asyncio.Task[Any]) -> None:
    """Cancel `task` and await its completion, suppressing `CancelledError`.

    If the task is already done, any attached exception is marked
    retrieved so the loop doesn't log a "Task exception was never
    retrieved" warning. The exception itself remains queryable via
    `task.exception()`. Non-cancellation exceptions raised during
    cancellation propagate to the caller.
    """
    if task.done():
        if not task.cancelled():
            # Flag the exception as retrieved to silence the loop warning.
            task.exception()
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


__all__ = [
    "cancel_and_wait",
    "fire_and_forget",
    "initialize_asyncio",
    "run_on_subprocess_capable_loop",
    "supervised_task",
]
