# Copyright 2026 Marimo. All rights reserved.
"""Evaluator — composes ExecutionLifecycles around an Executor."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._entrypoints.registry import EntryPointRegistry
from marimo._runtime.executor.executor import DefaultExecutor, Executor
from marimo._runtime.executor.lifecycles import ExecutionLifecycle, Skip
from marimo._runtime.runner.result import RunResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._ast.cell import CellImpl


LOGGER = _loggers.marimo_logger()


class Evaluator:
    """Compose ExecutionLifecycles around an Executor. Owns ``evaluate``."""

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
        completed: list[ExecutionLifecycle] = []
        skip: Skip | None = None
        result: RunResult | None = None

        try:
            for life in self.lifecycles:
                decision = life.setup(cell, glbls)
                completed.append(life)
                if isinstance(decision, Skip):
                    skip = decision
                    break
        except BaseException as e:
            result = RunResult(output=None, exception=e)

        if result is None:
            if skip is not None and skip.result is not None:
                # Lifecycle supplied a complete RunResult — preserve all
                # fields (output, accumulated_output, exception).
                result = skip.result
            elif skip is not None:
                result = RunResult(output=None, exception=None)
            else:
                try:
                    value = await self.executor.execute_cell_async(cell, glbls)
                    result = RunResult(output=value, exception=None)
                except BaseException as e:
                    result = RunResult(output=None, exception=e)

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
# values are **factories** (``Callable[[], Executor]``); the kernel
# calls the factory once to get an instance and hands it to an
# ``Evaluator``.
_EXECUTOR_REGISTRY: EntryPointRegistry[Callable[[], Executor]] = (
    EntryPointRegistry("marimo.cell.executor")
)


def resolve_executor() -> Executor:
    """Return the registered executor factory's product, or ``DefaultExecutor``.

    Used by both the kernel runner and script runner so a plugin
    registered against ``marimo.cell.executor`` takes effect for both.
    Only one factory is loaded — the alphabetically-first name across
    registered plugins and installed entry points (per
    ``EntryPointRegistry.names()``, which returns a sorted union).
    Others are noted via ``LOGGER.warning`` but never imported, so a
    broken third-party plugin doesn't take down notebook execution.

    If the selected factory itself raises on construction, we log and
    fall back to ``DefaultExecutor`` rather than propagate — a broken
    plugin shouldn't take down the kernel.
    """
    names = _EXECUTOR_REGISTRY.names()
    if not names:
        return DefaultExecutor()
    name, *additional = names
    if additional:
        LOGGER.warning(
            "multiple ``marimo.cell.executor`` factories registered; "
            "using %r and ignoring %d other(s)",
            name,
            len(additional),
        )
    try:
        return _EXECUTOR_REGISTRY.get(name)()
    except Exception as e:
        LOGGER.warning(
            "marimo.cell.executor factory %r failed to construct: %s; "
            "falling back to ``DefaultExecutor``.",
            name,
            e,
        )
        return DefaultExecutor()
