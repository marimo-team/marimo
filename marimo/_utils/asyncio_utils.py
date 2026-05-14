# Copyright 2026 Marimo. All rights reserved.
"""Small in-tree asyncio helpers.

- ``supervised_task`` / ``fire_and_forget``: create a task that won't be
  garbage-collected mid-flight and whose unhandled exceptions are logged
  instead of swallowed by the loop's default handler.
- ``cancel_and_wait``: the ``task.cancel(); await task`` /
  ``except CancelledError`` dance, in one place.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any, TypeVar

from marimo import _loggers

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")

# Module-level registry for fire_and_forget. The event loop holds only
# weak references to tasks; without a strong reference here the task can
# be garbage-collected mid-flight. The done-callback discards on
# completion, so this never grows unbounded under normal use.
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


def _log_task_exception(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        LOGGER.error(
            "Unhandled exception in background task %r",
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
    """Schedule ``coro`` with a strong reference and exception logging.

    Args:
        coro: The coroutine to schedule.
        name: Task name (shows up in logs and ``asyncio.all_tasks()``).
        registry: Optional set the task is added to and removed from on
            completion. Pass one for lifespan-scoped tracking.
        on_exception: Optional callback for unhandled exceptions. If
            omitted, exceptions are logged at error level.

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


def fire_and_forget(
    coro: Coroutine[Any, Any, Any], *, name: str
) -> asyncio.Task[Any] | None:
    """Schedule ``coro`` on the running loop; caller will not await it.

    If called from a thread with no running loop (tests, scripts), runs
    the coroutine to completion synchronously via ``asyncio.run`` and
    returns ``None``. This preserves best-effort event-emission
    semantics without forcing every caller to know which context it is in.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return None
    return supervised_task(coro, name=name, registry=_BACKGROUND_TASKS)


async def cancel_and_wait(task: asyncio.Task[Any]) -> None:
    """Cancel ``task`` and await its completion, suppressing ``CancelledError``.

    No-op if already done. Non-cancellation exceptions propagate.
    """
    if task.done():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


__all__ = [
    "cancel_and_wait",
    "fire_and_forget",
    "supervised_task",
]
