# Copyright 2026 Marimo. All rights reserved.
"""Evaluator — composes ExecutionLifecycles around an Executor."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import signal
import threading
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._entrypoints.registry import EntryPointRegistry
from marimo._runtime.control_flow import MarimoInterrupt
from marimo._runtime.executor.executor import DefaultExecutor, Executor
from marimo._runtime.executor.lifecycles import ExecutionLifecycle, Skip
from marimo._runtime.runner.result import RunResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from marimo._ast.cell import CellImpl


LOGGER = _loggers.marimo_logger()


class Evaluator:
    """Compose ExecutionLifecycles around an Executor. Owns `evaluate`."""

    def __init__(
        self,
        executor: Executor,
        lifecycles: list[ExecutionLifecycle] | None = None,
    ) -> None:
        self.executor = executor
        self.lifecycles: list[ExecutionLifecycle] = lifecycles or []

    async def evaluate(
        self, cell: CellImpl, glbls: dict[str, Any]
    ) -> RunResult:
        """Setup lifecycles, execute, and teardown lifecycles."""
        completed, skip, body_exc = self._setup_chain(cell, glbls)

        if body_exc is not None:
            result: RunResult = RunResult(output=None, exception=body_exc)
        elif skip is not None:
            # Lifecycle short-circuited — pass its full RunResult through
            # so ``accumulated_output`` and any other field survive.
            result = (
                skip.result
                if skip.result is not None
                else RunResult(output=None, exception=None)
            )
        else:
            try:
                value = await self.executor.execute_cell_async(cell, glbls)
                result = RunResult(output=value, exception=None)
            except BaseException as e:
                result = RunResult(output=None, exception=e)

        return self._teardown_chain(cell, glbls, completed, result)

    def evaluate_sync(
        self, cell: CellImpl, glbls: dict[str, Any]
    ) -> RunResult:
        """Sync mirror of ``evaluate`` — for callers without an event loop."""
        completed, skip, body_exc = self._setup_chain(cell, glbls)

        if body_exc is not None:
            result: RunResult = RunResult(output=None, exception=body_exc)
        elif skip is not None:
            result = (
                skip.result
                if skip.result is not None
                else RunResult(output=None, exception=None)
            )
        else:
            try:
                value = self.executor.execute_cell(cell, glbls)
                result = RunResult(output=value, exception=None)
            except BaseException as e:
                result = RunResult(output=None, exception=e)

        return self._teardown_chain(cell, glbls, completed, result)

    async def evaluate_interruptible(
        self, cell: CellImpl, glbls: dict[str, Any]
    ) -> RunResult:
        """Await ``evaluate`` with SIGINT capture for coroutine cells.

        SIGINT during an awaited coroutine raises in the event loop, not
        in the user's coroutine. Wrap the future so SIGINT cancels it.
        Sync cells and non-main-thread callers just await ``evaluate``.
        """
        if not cell.is_coroutine():
            return await self.evaluate(cell, glbls)
        future = asyncio.ensure_future(self.evaluate(cell, glbls))
        if threading.current_thread() is threading.main_thread():
            with _cancel_on_sigint(future):
                return await future
        return await future

    def _setup_chain(
        self, cell: CellImpl, glbls: dict[str, Any]
    ) -> tuple[list[ExecutionLifecycle], Skip | None, BaseException | None]:
        completed: list[ExecutionLifecycle] = []
        skip: Skip | None = None
        try:
            for life in self.lifecycles:
                decision = life.setup(cell, glbls)
                completed.append(life)
                if isinstance(decision, Skip):
                    skip = decision
                    break
        except BaseException as e:
            return completed, None, e
        return completed, skip, None

    def _teardown_chain(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        completed: list[ExecutionLifecycle],
        result: RunResult,
    ) -> RunResult:
        teardown_exc: BaseException | None = None
        for life in reversed(completed):
            try:
                life.teardown(cell, glbls, result)
            except BaseException as e:
                if teardown_exc is not None:
                    LOGGER.error(
                        "teardown exception overridden by later teardown: %s",
                        teardown_exc,
                    )
                teardown_exc = e

        if teardown_exc is not None:
            if result.exception is not None:
                LOGGER.warning(
                    "body exception suppressed by teardown raise: %s",
                    result.exception,
                )
            return replace(result, exception=teardown_exc)
        return result


# Public entry-point registry for plugin-loaded Executors. Registered
# values are **factories** (`Callable[[], Executor]`); the kernel
# calls the factory once to get an instance and hands it to an
# `Evaluator`.
_EXECUTOR_REGISTRY: EntryPointRegistry[Callable[[], Executor]] = (
    EntryPointRegistry("marimo.cell.executor")
)


def resolve_executor() -> Executor:
    """Return the registered executor factory's product, or `DefaultExecutor`.

    NB. Only one factory is loaded, with others logged for visibility.
    """
    names = _EXECUTOR_REGISTRY.names()
    if not names:
        return DefaultExecutor()
    name, *additional = names
    if additional:
        LOGGER.warning(
            "multiple `marimo.cell.executor` factories registered; "
            "using %r and ignoring %d other(s)",
            name,
            len(additional),
        )
    try:
        return _EXECUTOR_REGISTRY.get(name)()
    except Exception as e:
        LOGGER.warning(
            "marimo.cell.executor factory %r failed to construct: %s; "
            "falling back to `DefaultExecutor`.",
            name,
            e,
        )
        return DefaultExecutor()


# Adapted from
# https://github.com/ipython/ipykernel/blob/eddd3e666a82ebec287168b0da7cfa03639a3772/ipykernel/ipkernel.py#L312
@contextlib.contextmanager
def _cancel_on_sigint(future: asyncio.Future[Any]) -> Iterator[None]:
    """Cancel ``future`` if a SIGINT arrives during the ``with`` block.

    SIGINT raises in the event loop when running async code, but we want
    it to halt the coroutine. Ideally it would raise ``KeyboardInterrupt``,
    but this turns it into a ``CancelledError``.
    """
    sigint_future: asyncio.Future[int] = asyncio.Future()

    def cancel_unless_done(f: asyncio.Future[Any], _: Any) -> None:
        if f.cancelled() or f.done():
            return
        f.cancel()

    sigint_future.add_done_callback(
        functools.partial(cancel_unless_done, future)
    )
    future.add_done_callback(
        functools.partial(cancel_unless_done, sigint_future)
    )

    # Capture the previously-installed SIGINT handler *before* we install
    # ours so ``handle_sigint`` can invoke it for its side effects
    # (kernel broadcast, duckdb interrupt). For async cells the actual
    # halt comes from cancelling the future, not from a raised
    # ``MarimoInterrupt`` — so we swallow that here.
    prior_sigint = signal.getsignal(signal.SIGINT)

    def handle_sigint(signum: int, frame: Any) -> None:
        if sigint_future.cancelled() or sigint_future.done():
            return
        sigint_future.set_result(1)
        if callable(prior_sigint):
            try:
                prior_sigint(signum, frame)
            except MarimoInterrupt:
                # The kernel's handler raises MarimoInterrupt for sync
                # halt; we cancel the future instead.
                pass

    save_sigint = signal.signal(signal.SIGINT, handle_sigint)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, save_sigint)
