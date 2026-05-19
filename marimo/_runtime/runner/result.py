# Copyright 2026 Marimo. All rights reserved.
"""The value type a cell produces when it runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from marimo._runtime.runner.hook_context import ExceptionOrError


@dataclass
class RunResult:
    # Raw output of cell: last expression
    output: Any
    # Exception raised by cell, if any
    #
    # TODO(akshayka): Exceptions and "Errors" (most of which are at parse time
    # and can't be encountered by the runner) shouldn't be packed into a single
    # field.
    exception: ExceptionOrError | None
    # Accumulated output: via imperative mo.output.append()
    accumulated_output: Any = None

    def success(self) -> bool:
        """Whether the cell expected successfully"""
        return self.exception is None
