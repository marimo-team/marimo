# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.parse import NotebookSerialization
from marimo._lint.rules.base import LintError, LintRule, Severity
from marimo._schemas.serialization import UnparsableCell


class UnparsableRule(LintRule):
    """MB001: Cell contains unparsable code."""

    def __init__(self):
        super().__init__(
            code="MB001",
            name="unparsable-cells",
            description="Cell contains unparsable code",
            severity=Severity.BREAKING,
            fixable=False,
        )

    def check(self, notebook: NotebookSerialization) -> list[LintError]:
        """Check for unparsable cells."""
        errors = []

        for cell in notebook.cells:
            if isinstance(cell, UnparsableCell):  # Unparsable cell
                # Try to find the line number of the error
                line_num = cell.lineno
                col_num = cell.col_offset

                errors.append(
                    LintError(
                        code=self.code,
                        name=self.name,
                        message="Notebook contains unparsable code",
                        severity=self.severity,
                        cell_id=None,
                        line=line_num,
                        column=col_num,
                        fixable=False,
                    )
                )

        return errors
