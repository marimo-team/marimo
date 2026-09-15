# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._runtime import output
from marimo._runtime.context.utils import running_in_notebook
from marimo._utils.flatten import contains_instance

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._runtime.runner.hook_context import PostExecutionHookContext
    from marimo._runtime.runner.result import RunResult

LOGGER = _loggers.marimo_logger()


# Imports are cached before notebook execution; mount in the importing cell.
def mount_lens(
    cell: CellImpl, ctx: PostExecutionHookContext, result: RunResult
) -> None:
    if (
        not result.success()
        or not running_in_notebook()
        or cell.namespace_to_variable("marimo") is None
    ):
        return

    try:
        try:
            from marimo_lens import Lens  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            if exc.name != "marimo_lens":
                raise
            return

        if any(
            contains_instance(other.output, Lens)
            for other in ctx.graph.cells.values()
        ):
            return

        lens = Lens()
        cell.set_output((cell.output, lens))
        if result.output is not None:
            output.append(result.output)
        output.append(lens)
    except Exception:
        LOGGER.warning(
            "Failed to automatically mount marimo-lens", exc_info=True
        )
