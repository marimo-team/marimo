# Copyright 2026 Marimo. All rights reserved.
"""Evaluator composes ExecutionLifecycles around an Executor."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._entrypoints.registry import EntryPointRegistry
from marimo._runtime.executor.executor import DefaultExecutor, Executor
from marimo._runtime.executor.lifecycles import ExecutionLifecycle, Skip
from marimo._runtime.runner.result import RunResult
from marimo._types.globals import MutableGlobals

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._ast.cell import CellImpl


LOGGER = _loggers.marimo_logger()


class Evaluator:
    """Run a cell through an `Executor`, wrapped in `ExecutionLifecycles`."""

    def __init__(
        self,
        executor: Executor,
        lifecycles: list[ExecutionLifecycle],
    ) -> None:
        self.executor = executor
        self.lifecycles: list[ExecutionLifecycle] = lifecycles

    async def evaluate(
        self, cell: CellImpl, glbls: MutableGlobals
    ) -> RunResult:
        """Compose `ExecutionLifecycle`s around an `Executor` run.

        Lifecycle `setup`s run in order; a returned `Skip` short-circuits the
        body. `teardown`s run in reverse order on lifecycles whose `setup`
        was reached.
        """
        completed, skip, body_exc = self._setup_chain(cell, glbls)

        if body_exc is not None:
            result: RunResult = RunResult(output=None, exception=body_exc)
        elif skip is not None:
            # Lifecycle short-circuited — pass its full RunResult through
            # so `accumulated_output` and any other field survive.
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
        self, cell: CellImpl, glbls: MutableGlobals
    ) -> RunResult:
        """`evaluate` for callers without an event loop."""
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

    def _setup_chain(
        self, cell: CellImpl, glbls: MutableGlobals
    ) -> tuple[list[ExecutionLifecycle], Skip | None, BaseException | None]:
        """Run each lifecycle's `setup` in order.

        Runs `setup` on each lifecycle in `self.lifecycles` until one returns a
        `Skip` or one raises an exception. Returns a tuple of (completed
        lifecycles, first Skip if any, first exception if any).
        """
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
        glbls: MutableGlobals,
        completed: list[ExecutionLifecycle],
        result: RunResult,
    ) -> RunResult:
        """Run each lifecycle's `teardown` in order.

        Runs `teardown` on each lifecycle in `self.lifecycles` in reverse order,
        on lifecycles who successfully ran `setup`. Returns a `RunResult` with
        the first exception raised by a `teardown`.
        """
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
