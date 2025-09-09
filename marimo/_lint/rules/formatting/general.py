# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.parse import NotebookSerialization
from marimo._lint.rules.base import LintError, LintRule, Severity


class GeneralFormattingRule(LintRule):
    """MF001: General formatting issues."""

    def __init__(self):
        super().__init__(
            code="MF001",
            name="general-formatting",
            description="General formatting issues with the notebook format.",
            severity=Severity.FORMATTING,
            fixable=True,
        )

    def check(self, notebook: NotebookSerialization) -> list[LintError]:
        """Check for general formatting issues by extracting violations from serialization."""
        errors = []

        # Import the violation constants to check for specific types
        from marimo._ast.parse import (
            EXPECTED_GENERATED_WITH_VIOLATION,
            UNEXPECTED_STATEMENT_APP_INIT_VIOLATION,
            UNEXPECTED_STATEMENT_CELL_DEF_VIOLATION,
            UNEXPECTED_STATEMENT_MARIMO_IMPORT_VIOLATION,
        )

        # Extract violations from the notebook serialization
        for violation in notebook.violations:
            # Determine if this violation is fixable
            is_fixable = violation.description in [
                UNEXPECTED_STATEMENT_CELL_DEF_VIOLATION,
                UNEXPECTED_STATEMENT_MARIMO_IMPORT_VIOLATION,
                EXPECTED_GENERATED_WITH_VIOLATION,
                UNEXPECTED_STATEMENT_APP_INIT_VIOLATION,
            ]

            # Convert Violation to LintError
            errors.append(
                LintError(
                    code=self.code,
                    name=self.name,
                    message=violation.description,
                    severity=self.severity,
                    cell_id=[],  # Violations don't have cell_id
                    line=violation.lineno,
                    column=violation.col_offset
                    + 1,  # Convert 0-based to 1-based
                    fixable=is_fixable,
                )
            )

        return errors
