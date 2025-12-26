# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule
from marimo._schemas.serialization import UnparsableCell

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class UnparsableRule(LintRule):
    """MB001: Cell contains unparsable code.

    This rule detects cells that contain code that cannot be parsed as valid Python.
    Unparsable cells typically occur when a notebook file is corrupted, contains invalid
    syntax, or has encoding issues that prevent proper parsing.

    ## What it does

    Identifies cells that cannot be parsed into valid Python AST nodes, indicating
    fundamental syntax or encoding problems that prevent the notebook from being loaded.

    ## Why is this bad?

    Unparsable cells prevent the notebook from running as a script and will throw
    errors when executed in notebook mode. While marimo can still open the notebook,
    these cells cannot be run until the parsing issues are resolved.

    ## Examples

    **Problematic:**
    ```python
    # Cell with encoding issues or corrupt data
    x = 1 \\x00\\x01\\x02  # Binary data in source
    ```

    **Problematic:**
    ```python
    # Cell with fundamental syntax errors
    def func(
        # Missing closing parenthesis and body
    ```

    **Solution:**
    ```python
    # Fix syntax errors and encoding issues
    def func():
        return 42
    ```

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    """

    code = "MB001"
    name = "unparsable-cells"
    description = "Cell contains unparsable code"
    severity = Severity.BREAKING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Check for unparsable cells."""
        for cell in ctx.notebook.cells:
            if isinstance(cell, UnparsableCell):  # Unparsable cell
                # Try to find the line number of the error
                line_num = cell.lineno
                col_num = cell.col_offset

                diagnostic = Diagnostic(
                    message="Notebook contains unparsable code",
                    cell_id=None,
                    line=line_num,
                    column=col_num,
                )

                await ctx.add_diagnostic(diagnostic)
