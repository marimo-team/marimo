# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import List

from marimo._lint.base import LintError, LintRule, Severity
from marimo._ast.parse import NotebookSerialization


class GeneralFormattingRule(LintRule):
    """MF001: General formatting issues."""

    def __init__(self):
        super().__init__(
            code="MF001",
            name="general-formatting",
            description="General formatting issues (trailing whitespace, inconsistent spacing)",
            severity=Severity.FORMATTING,
            fixable=True,
        )

    def check(self, notebook: NotebookSerialization) -> List[LintError]:
        """Check for general formatting issues by extracting violations from serialization."""
        errors = []

        # Import the violation constants to check for specific types
        from marimo._ast.parse import (
            UNEXPECTED_STATEMENT_CELL_DEF_VIOLATION,
            UNEXPECTED_STATEMENT_MARIMO_IMPORT_VIOLATION,
            EXPECTED_GENERATED_WITH_VIOLATION,
            UNEXPECTED_STATEMENT_APP_INIT_VIOLATION,
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
