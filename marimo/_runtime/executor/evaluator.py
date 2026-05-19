# Copyright 2026 Marimo. All rights reserved.
"""Evaluator — composes ExecutionLifecycles around an Executor."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class EvaluatorConfig:
    """Configuration for building an Evaluator."""

    executor: Executor = field(default_factory=DefaultExecutor)
    lifecycles: list[ExecutionLifecycle] = field(default_factory=list)


class Evaluator:
    """Compose ExecutionLifecycles around an Executor. Owns ``evaluate``."""

    def __init__(
        self,
        executor: Executor,
        lifecycles: list[ExecutionLifecycle] | None = None,
    ) -> None:
        self.executor = executor
        self.lifecycles: list[ExecutionLifecycle] = lifecycles or []

    async def evaluate(self, cell: CellImpl, glbls: dict[str, Any]) -> Any:
        """Setup lifecycles, execute, and teardown lifecycles."""
        completed: list[ExecutionLifecycle] = []
        skip: Skip | None = None
        body_exc: BaseException | None = None
        value: Any = None

        try:
            for life in self.lifecycles:
                decision = life.setup(cell, glbls)
                completed.append(life)
                if isinstance(decision, Skip):
                    skip = decision
                    break
        except BaseException as e:
            body_exc = e

        # async and non-async pass through this path.
        if body_exc is None:
            if skip is not None:
                value = skip.value
            else:
                try:
                    value = await self.executor.execute_cell_async(cell, glbls)
                except BaseException as e:
                    body_exc = e

        result = RunResult(output=value, exception=body_exc)
        exc: BaseException | None = None
        for life in reversed(completed):
            try:
                life.teardown(cell, glbls, result)
            except BaseException as e:
                if exc is not None:
                    LOGGER.error(
                        "teardown exception overridden by later teardown: %s",
                        exc,
                    )
                exc = e

        if exc is not None:
            if body_exc is not None:
                LOGGER.warning(
                    "body exception suppressed by teardown raise: %s",
                    body_exc,
                )
            raise exc
        if body_exc is not None:
            raise body_exc
        return value


def build_evaluator(config: EvaluatorConfig) -> Evaluator:
    """One-liner: hand instances from config to the Evaluator."""
    return Evaluator(executor=config.executor, lifecycles=config.lifecycles)


# Public entry-point registry for plugin-loaded Executors. Registered
# values are **factories** (``Callable[[], Executor]``); the kernel
# calls the factory once to get an instance, then places it in an
# ``EvaluatorConfig``.
_EXECUTOR_REGISTRY: EntryPointRegistry[Callable[[], Executor]] = (
    EntryPointRegistry("marimo.cell.executor")
)
