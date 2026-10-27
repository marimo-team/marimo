# Copyright 2026 Marimo. All rights reserved.
"""Small in-tree asyncio helpers.

- `supervised_task` / `fire_and_forget`: create a task that won't be
  garbage-collected mid-flight and whose non-cancellation exceptions
  are always logged on completion (intended for fire-and-forget work
  where the loop's default handler would otherwise swallow them).
- `cancel_and_wait`: the `task.cancel(); await task` /
  `except CancelledError` dance, in one place.
- `run_coroutine_blocking`: `asyncio.run` that also works when the
  calling thread already has a running loop.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import sys
import threading
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


def run_coroutine_blocking(
    coro: Coroutine[Any, Any, T],
    *,
    thread_name: str = "marimo-blocking-coroutine",
) -> T:
    """Run `coro` to completion and return its result, blocking the caller.

    Behaves like `asyncio.run` when the calling thread has no running event
    loop. When a loop *is* already running, `asyncio.run` raises
    `RuntimeError`, so the coroutine is driven on a dedicated worker thread
    with its own loop while the calling thread blocks on the result. This
    lets synchronous APIs stay synchronous when they're called from async
    code, instead of failing outright.

    The caller's loop is blocked for the duration, so this is only
    appropriate for APIs that are synchronous by contract.

    Note that `coro` may run on a different thread than the caller. Anything
    it needs from thread-local state (such as marimo's runtime context) has
    to be established inside `coro` itself.
    """

    def _run() -> T:
        # Match the selector-loop policy marimo relies on elsewhere; only
        # done on paths that actually create a loop.
        initialize_asyncio()
        return asyncio.run(coro)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run()

    # A bare thread rather than a ThreadPoolExecutor: the executor's
    # context manager shuts down with `wait=True`, so a KeyboardInterrupt
    # while the caller is blocked would hang until the nested run finished.
    # `Future.result()` waits on a condition variable, which the interrupt
    # can break out of, and a daemon thread doesn't hold up interpreter
    # exit. The Future also re-raises with the worker's traceback intact.
    future: concurrent.futures.Future[T] = concurrent.futures.Future()

    def _target() -> None:
        try:
            future.set_result(_run())
        except BaseException as exc:
            future.set_exception(exc)

    threading.Thread(target=_target, name=thread_name, daemon=True).start()
    return future.result()


__all__ = [
    "cancel_and_wait",
    "fire_and_forget",
    "initialize_asyncio",
    "run_coroutine_blocking",
    "supervised_task",
]
