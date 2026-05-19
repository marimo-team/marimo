# Copyright 2026 Marimo. All rights reserved.
"""Per-cell setup/teardown lifecycles owned by the Evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._runtime.runner.result import RunResult


@dataclass
class Skip:
    """Returned from ``ExecutionLifecycle.setup`` to short-circuit the body."""

    value: Any = None


class ExecutionLifecycle(Protocol):
    """Per-cell setup/teardown wrap."""

    name: str

    def setup(self, cell: CellImpl, glbls: dict[str, Any]) -> Skip | None: ...

    def teardown(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        run_result: RunResult,
    ) -> None: ...


def _builtin_lifecycles() -> dict[str, type[ExecutionLifecycle]]:
    """Built-in lifecycles keyed by name."""
    from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

    return {StrictLifecycle.name: StrictLifecycle}


def get_lifecycle_class(name: str) -> type[ExecutionLifecycle]:
    """Look up a built-in lifecycle class by name. Raises KeyError on miss."""
    return _builtin_lifecycles()[name]
