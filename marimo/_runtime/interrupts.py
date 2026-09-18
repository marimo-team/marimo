# Copyright 2026 Marimo. All rights reserved.
"""Controls where Ctrl-C can raise.

Ctrl-C can arrive at any line of Python. If it raises inside marimo's own
code, cells get stuck or the kernel deadlocks. So the signal handler only
sets a flag, and that flag becomes an exception only inside a `guard`
around user code. Between cells it just stops the queue.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from marimo import _loggers
from marimo._messaging.notification import InterruptedNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.context.types import RuntimeContext, safe_get_context
from marimo._runtime.control_flow import MarimoInterrupt

if TYPE_CHECKING:
    from collections.abc import Coroutine, Iterator

    from typing_extensions import Self

    from marimo._messaging.types import Stream

LOGGER = _loggers.marimo_logger()
T = TypeVar("T")


class InterruptScope:
    """Tracks whether one run or one callback was interrupted.

    ```python
    with InterruptScope() as interrupts:
        with suppress(MarimoInterrupt), interrupts.guard():
            callback()  # Ctrl-C raises here
        result = await interrupts.run(coro())  # Ctrl-C cancels this
        cleanup()  # Ctrl-C never raises here
    ```

    Ctrl-C raises `MarimoInterrupt` inside `guard` and `run`, and sets
    `interrupted` on the way out. Anywhere else it only sets `interrupted`.
    A caller that must not start new work after Ctrl-C checks that flag
    as the first line inside the guard.

    If one scope is opened inside another, Ctrl-C raises in the inner one
    and marks both as interrupted.
    """

    def __init__(self) -> None:
        self.interrupted = False
        self._target: asyncio.Task[Any] | Literal["sync"] | None = None
        self._context: RuntimeContext | None = None
        self._previous: InterruptScope | None = None
        self._stream: Stream | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._report_pending = False
        self._cancel_requested = False
        self._connection_error: Exception | None = None

    def __enter__(self) -> Self:
        ctx = safe_get_context()
        if ctx is not None:
            self._context = ctx
            self._stream = ctx.stream
            self._previous = ctx.interrupt_scope
            ctx.interrupt_scope = self
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._target = None
        try:
            # Report before another operation can install a new stdin prompt.
            self._report()
        finally:
            if self._context is not None:
                self._context.interrupt_scope = self._previous

    def request(self) -> None:
        """Called by the SIGINT handler."""
        scope: InterruptScope | None = self
        while scope is not None:
            scope.interrupted = True
            scope = scope._previous
        if not self._report_pending:
            self._report_pending = True
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._report)

        target = self._target
        if target is None:
            return

        ctx = self._context
        execution = ctx.execution_context if ctx is not None else None
        if execution is not None and execution.duckdb_connection is not None:
            try:
                execution.duckdb_connection.interrupt()
            except Exception as exc:
                self._connection_error = exc

        if target == "sync":
            raise MarimoInterrupt
        self._cancel_requested = True
        target.get_loop().call_soon_threadsafe(target.cancel)

    @contextmanager
    def guard(self) -> Iterator[None]:
        """Ctrl-C raises `MarimoInterrupt` inside this block."""
        previous = self._target
        try:
            self._target = "sync"
            yield
        except MarimoInterrupt:
            self.interrupted = True
            raise
        finally:
            self._target = previous

    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run async user code in its own task so Ctrl-C can cancel it.

        Raises `MarimoInterrupt` if Ctrl-C cancelled it or had already
        happened. If the caller's own task is cancelled instead,
        `CancelledError` propagates as usual.
        """
        if self.interrupted:
            coro.close()
            raise MarimoInterrupt
        previous = self._target
        self._target = None
        self._cancel_requested = False
        try:
            task = asyncio.create_task(coro)
            self._target = task
            # Ctrl-C during task creation must not admit new work.
            if self.interrupted:
                self._cancel_requested = True
                task.cancel()
            try:
                return await task
            except asyncio.CancelledError as exc:
                # Cancelling the awaiting task also cancels `task`, so the
                # child's state can't tell us who asked. Our flag can.
                if not self._cancel_requested:
                    raise
                self.interrupted = True
                raise MarimoInterrupt from exc
        finally:
            self._target = previous

    def _report(self) -> None:
        if not self._report_pending:
            return
        self._report_pending = False
        LOGGER.info("Interrupt request received")
        if self._connection_error is not None:
            LOGGER.warning(
                "Failed to interrupt running duckdb connection: %s",
                self._connection_error,
            )
            self._connection_error = None
        if self._stream is not None:
            broadcast_notification(InterruptedNotification(), self._stream)
