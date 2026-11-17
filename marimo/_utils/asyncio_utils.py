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
- `ProactorLoop` / `run_on_proactor_loop`: run coroutines that start
  subprocesses, such as Playwright calls, on Windows, where marimo's
  SelectorEventLoop cannot.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import functools
import sys
import threading
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from marimo import _loggers

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from contextlib import AbstractAsyncContextManager
    from types import TracebackType
    from typing import Self

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")
P = ParamSpec("P")

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


class ProactorLoop:
    """Run coroutines that start subprocesses, such as Playwright calls.

    On Windows, marimo's SelectorEventLoop cannot create subprocesses, so
    `run` executes each coroutine on a ProactorEventLoop in a worker thread
    while the caller's loop keeps serving marimo sessions. Objects those
    coroutines create, such as a Playwright page, are bound to the worker
    loop: use them only inside coroutines passed to `run`. On other
    platforms, `run` awaits on the caller's loop.

    ```python
    async with ProactorLoop() as browser_loop:
        page = await browser_loop.enter_async_context(open_page())
        await browser_loop.run(page.goto(url))
    ```
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._contexts = contextlib.AsyncExitStack()

    async def __aenter__(self) -> Self:
        if sys.platform != "win32":
            return self
        ready: concurrent.futures.Future[asyncio.AbstractEventLoop] = (
            concurrent.futures.Future()
        )

        def serve() -> None:
            # Built here, because a ProactorEventLoop created on the main
            # thread takes over its signal wakeup fd.
            try:
                # Closing the runner cancels and awaits the tasks left on it.
                with asyncio.Runner(
                    loop_factory=asyncio.ProactorEventLoop
                ) as runner:
                    loop = runner.get_loop()
                    if ready.set_running_or_notify_cancel():
                        ready.set_result(loop)
                        loop.run_forever()
            except BaseException as exc:
                if ready.done():
                    raise
                ready.set_exception(exc)

        self._thread = threading.Thread(
            target=serve, name="marimo-proactor-loop", daemon=True
        )
        self._thread.start()
        try:
            loop = await asyncio.wrap_future(ready)
        except BaseException:
            # The worker may have started its loop before the cancellation.
            if not ready.cancel():
                loop = ready.result()
                loop.call_soon_threadsafe(loop.stop)
            raise
        self._loop = loop
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            await self.run(self._contexts.__aexit__(exc_type, exc, traceback))
        finally:
            if self._loop is not None and self._thread is not None:
                self._loop.call_soon_threadsafe(self._loop.stop)
                await asyncio.to_thread(self._thread.join)

    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Await `coro` on the loop that can start subprocesses.

        Cancelling the call cancels `coro` and waits for it to unwind.
        """
        loop = self._loop
        if loop is None:
            return await coro
        done: concurrent.futures.Future[T] = concurrent.futures.Future()
        tasks: list[asyncio.Task[T]] = []

        def start() -> None:
            task = loop.create_task(coro)
            task.add_done_callback(functools.partial(_copy_task_state, done))
            tasks.append(task)

        # Callbacks run in order on the worker, so `start` precedes a cancel.
        loop.call_soon_threadsafe(start)
        waiter = asyncio.wrap_future(done)
        try:
            return await asyncio.shield(waiter)
        except asyncio.CancelledError:
            loop.call_soon_threadsafe(lambda: tasks[0].cancel())
            # Let `coro` unwind, as it would on the caller's loop, then discard
            # its outcome. After Ctrl+C that is often a closed-browser error.
            await asyncio.wait([waiter])
            if not waiter.cancelled() and (error := waiter.exception()):
                LOGGER.debug(
                    "Cancelled call failed while unwinding: %r", error
                )
            raise

    async def enter_async_context(
        self, context: AbstractAsyncContextManager[T]
    ) -> T:
        """Enter `context` with `run`, and exit it when the block exits."""
        return await self.run(self._contexts.enter_async_context(context))


def _copy_task_state(
    future: concurrent.futures.Future[T], task: asyncio.Task[T]
) -> None:
    if task.cancelled():
        future.cancel()
    elif (exc := task.exception()) is not None:
        future.set_exception(exc)
    else:
        future.set_result(task.result())


def run_on_proactor_loop(
    func: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, Coroutine[Any, Any, T]]:
    """Decorate an async function so that each call runs in a `ProactorLoop`.

    The arguments and result must not be bound to the caller's loop, and
    callbacks passed in run on the worker thread. On platforms other than
    Windows, `func` is returned unchanged.
    """
    if sys.platform != "win32":
        return func

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        async with ProactorLoop() as loop:
            return await loop.run(func(*args, **kwargs))

    return wrapper


__all__ = [
    "ProactorLoop",
    "cancel_and_wait",
    "fire_and_forget",
    "initialize_asyncio",
    "run_coroutine_blocking",
    "run_on_proactor_loop",
    "supervised_task",
]
