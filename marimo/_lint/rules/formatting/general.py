# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class GeneralFormattingRule(LintRule):
    """MF001: General formatting issues with the notebook format.

    This rule detects violations in the marimo notebook file format that affect
    the structure and metadata of the notebook. These issues typically arise
    when notebook files are manually edited or corrupted during parsing.

    ## What it does

    Examines the notebook serialization for structural violations such as:
    - Missing or incorrect marimo import statements
    - Improperly formatted cell definitions
    - Missing app initialization code
    - Incorrect file generation metadata

    ## Why is this bad?

    Format violations can prevent marimo from properly loading or executing
    notebooks. While these don't affect the Python code logic, formatting errors
    mark a deviation in the expected script structure, which can lead to
    unexpected behavior when run as a script, or when loading the notebook.

    ## Examples

    **Problematic:**
    ```python
    # Missing marimo import
    @app.cell
    def __():
        return


    if __name__ == "__main__":
        app.run()
    ```

    **Solution:**
    ```python
    import marimo

    __generated_with = "0.1.0"
    app = marimo.App()


    @app.cell
    def __():
        return


    if __name__ == "__main__":
        app.run()
    ```

    **Note:** Most format issues are automatically fixable with `marimo check --fix`.

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [File Format Documentation](https://docs.marimo.io/guides/coming_from/jupyter/#marimo-file-format)
    """

    code = "MF001"
    name = "general-formatting"
    description = "General formatting issues with the notebook format."
    severity = Severity.FORMATTING
    fixable = True

    async def check(self, ctx: RuleContext) -> None:
        """Check for general formatting issues by extracting violations from serialization."""
        # Import the violation constants to check for specific types
        from marimo._ast.parse import (
            EXPECTED_GENERATED_WITH_VIOLATION,
            UNEXPECTED_STATEMENT_APP_INIT_VIOLATION,
            UNEXPECTED_STATEMENT_CELL_DEF_VIOLATION,
            UNEXPECTED_STATEMENT_MARIMO_IMPORT_VIOLATION,
        )

        # Extract violations from the notebook serialization
        for violation in ctx.notebook.violations:
            # Determine if this violation is fixable
            is_fixable = violation.description in [
                UNEXPECTED_STATEMENT_CELL_DEF_VIOLATION,
                UNEXPECTED_STATEMENT_MARIMO_IMPORT_VIOLATION,
                EXPECTED_GENERATED_WITH_VIOLATION,
                UNEXPECTED_STATEMENT_APP_INIT_VIOLATION,
            ]

            # Create diagnostic and add to context
            diagnostic = Diagnostic(
                message=violation.description,
                cell_id=[],  # Violations don't have cell_id
                line=violation.lineno - 1,  # Convert 1-based to 0-based
                column=violation.col_offset + 1,
                fixable=is_fixable,
            )

            await ctx.add_diagnostic(diagnostic)
