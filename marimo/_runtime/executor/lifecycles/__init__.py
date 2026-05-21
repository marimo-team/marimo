# Copyright 2026 Marimo. All rights reserved.
"""Per-cell setup/teardown lifecycles owned by the Evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from marimo._runtime.runner.result import RunResult
from marimo._types.globals import MutableGlobals

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl


@dataclass
class Skip:
    """Returned from `ExecutionLifecycle.setup` to short-circuit the body.

    `result` is the cell's `RunResult`; lifecycles can use this to
    inject a cache hit or a pre-failed result without running the body.
    `None` means the lifecycle wants to skip but has no associated run
    (output stays `None`, no exception).
    """

    result: RunResult | None = None


class ExecutionLifecycle(Protocol):
    """Per-cell setup/teardown wrap."""

    name: str

    def setup(self, cell: CellImpl, glbls: MutableGlobals) -> Skip | None: ...

    def teardown(
        self,
        cell: CellImpl,
        glbls: MutableGlobals,
        run_result: RunResult,
    ) -> None: ...
