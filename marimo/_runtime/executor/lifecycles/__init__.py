# Copyright 2026 Marimo. All rights reserved.
"""Per-cell execution lifecycles setup/teardown wraps around cell execution."""

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
    """Per-cell setup/teardown wrap for cell execution.

    `setup`s fire in composition order; `teardown`s fire in reverse
    order over the lifecycles whose `setup` was reached. Per-cell state
    is stashed on the instance.
    """

    name: str

    def setup(self, cell: CellImpl, glbls: MutableGlobals) -> Skip | None:
        """Run before the cell body.

        May mutate `glbls`. Return `Skip` to short-circuit the body (and
        any later lifecycle in the chain); return `None` to continue.
        Raising is treated like a body exception — the chain unwinds via
        `teardown` on the lifecycles whose `setup` was reached.
        """
        ...

    def teardown(
        self,
        cell: CellImpl,
        glbls: MutableGlobals,
        run_result: RunResult,
    ) -> None:
        """Run after the body (or after a `Skip`), in reverse composition order.

        May mutate `glbls`. Receives the final `RunResult` from the body or
        `Skip`. Raising from `teardown` replaces `run_result.exception`; the
        original body exception (if any) is logged and suppressed.
        """
        ...
