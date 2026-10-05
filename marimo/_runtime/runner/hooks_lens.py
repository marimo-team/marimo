# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._runtime import output

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._runtime.runner.hook_context import PostExecutionHookContext
    from marimo._runtime.runner.result import RunResult

LOGGER = _loggers.marimo_logger()


# Imports are cached before notebook execution; mount in the importing cell.
# marimo-lens decides whether the notebook needs a Lens.
def mount_lens(
    cell: CellImpl, ctx: PostExecutionHookContext, result: RunResult
) -> None:
    del ctx
    if not result.success() or cell.namespace_to_variable("marimo") is None:
        return

    try:
        try:
            from marimo_lens import (  # type: ignore[import-not-found]
                automatic_lens,
            )
        except ImportError as exc:
            # Also covers a marimo-lens release without automatic_lens.
            if exc.name != "marimo_lens":
                raise
            return

        lens = automatic_lens()
        if lens is None:
            return
        cell.set_output((cell.output, lens))
        if result.output is not None:
            output.append(result.output)
        output.append(lens)
    except Exception:
        LOGGER.warning(
            "Failed to automatically mount marimo-lens", exc_info=True
        )
