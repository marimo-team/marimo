# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule
from marimo._schemas.serialization import UnparsableCell

if TYPE_CHECKING:
    from marimo._lint.context import LintContext


class UnparsableRule(LintRule):
    """MB001: Cell contains unparsable code."""

    def __init__(self) -> None:
        super().__init__(
            code="MB001",
            name="unparsable-cells",
            description="Cell contains unparsable code",
            severity=Severity.BREAKING,
            fixable=False,
        )

    async def check(self, ctx: LintContext) -> None:
        """Check for unparsable cells."""
        for cell in ctx.notebook.cells:
            if isinstance(cell, UnparsableCell):  # Unparsable cell
                # Try to find the line number of the error
                line_num = cell.lineno
                col_num = cell.col_offset

                diagnostic = Diagnostic(
                    code=self.code,
                    name=self.name,
                    message="Notebook contains unparsable code",
                    severity=self.severity,
                    cell_id=None,
                    line=line_num,
                    column=col_num,
                    fixable=False,
                )

                await ctx.add_diagnostic(diagnostic)
