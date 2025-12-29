# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._ast.errors import ImportStarError
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._schemas.serialization import CellDef

IMPORT_STAR_ERROR_MESSAGE = (
    "Importing symbols with `import *` is not allowed in marimo."
)
IMPORT_STAR_HINT = (
    "Star imports are incompatible with marimo's reactive execution. Use "
    "'import module' and access members with dot notation instead. See: "
    "https://docs.marimo.io/guides/understanding_errors/import_star/"
)


class SyntaxErrorRule(LintRule):
    """MB005: Cell contains code that throws a SyntaxError on compilation.

    This rule detects cells that contain Python code with syntax errors that
    prevent compilation. Unlike unparsable cells (MB001), these cells can be
    parsed but fail when Python tries to compile them into executable code.

    ## What it does

    Attempts to compile each cell using marimo's internal compiler and catches any
    SyntaxError exceptions that occur during the compilation process.

    ## Why is this bad?

    Cells with syntax errors cannot be executed, making the notebook non-functional.
    SyntaxErrors prevent marimo from creating the dependency graph and running the
    reactive execution system, breaking the core functionality of the notebook.

    ## Examples

    **Problematic:**
    ```python
    # Invalid indentation
    if True:
    print("Hello")  # Missing indentation
    ```

    **Problematic:**
    ```python
    # Invalid syntax
    x = 1 +  # Missing operand
    ```

    **Problematic:**
    ```python
    # Mismatched brackets
    my_list = [1, 2, 3  # Missing closing bracket
    ```

    **Solution:**
    ```python
    # Fix indentation
    if True:
        print("Hello")  # Proper indentation
    ```

    **Solution:**
    ```python
    # Complete expressions
    x = 1 + 2  # Complete arithmetic expression
    ```

    **Solution:**
    ```python
    # Match brackets
    my_list = [1, 2, 3]  # Proper closing bracket
    ```

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Python SyntaxError Documentation](https://docs.python.org/3/tutorial/errors.html#syntax-errors)
    """

    code = "MB005"
    name = "invalid-syntax"
    description = "Cell contains code that throws a SyntaxError on compilation"
    severity = Severity.BREAKING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Check for syntax errors during compilation."""
        for e, cell in ctx.get_errors("SyntaxError"):
            if isinstance(e, ImportStarError):
                line, column = _handle_import_star_error(e, cell)
                await ctx.add_diagnostic(
                    Diagnostic(
                        message=IMPORT_STAR_ERROR_MESSAGE,
                        line=line,
                        column=column,
                        fix=IMPORT_STAR_HINT,
                    )
                )
            else:
                # Handle SyntaxError specifically
                if isinstance(e, SyntaxError):
                    message = f"{e.msg}"
                    line = cell.lineno + (e.lineno or 1) - 1
                    column = e.offset or 1
                else:
                    # For other exceptions, use string representation
                    message = str(e)
                    line = cell.lineno
                    column = 1
                await ctx.add_diagnostic(
                    Diagnostic(
                        message=message,
                        line=line,
                        column=column,
                        fix=_get_known_hints(message),
                    )
                )


def _handle_import_star_error(
    e: ImportStarError, cell: CellDef
) -> tuple[int, int]:
    """Handle ImportStarError and extract correct line number and clean message."""
    import re

    message_str = str(e)
    # The message format is "line {lineno} SyntaxError: ..." Extract the
    # relative line number and compute actual line
    actual_line = None
    if "..." not in message_str:
        line_match = re.match(r"line (\d+)", message_str)
        if line_match:
            relative_line = int(line_match.group(1))
            actual_line = cell.lineno + relative_line - 1
    if actual_line is None:
        actual_line = cell.lineno
        # Find the * in the cell source
        star_index = cell.code.find("*")
        if star_index != -1:
            # Count newlines before the star to get the line number
            actual_line += cell.code[:star_index].count("\n")

    # Clean message without "SyntaxError:" prefix
    column = getattr(e, "offset", 1) or 1

    return actual_line, column


def _get_known_hints(message: str) -> str | None:
    if message == "'return' outside function":
        return (
            "marimo cells are not normal Python functions; treat cell bodies "
            "as top-level code, or use `@app.function` to define a pure "
            "function."
        )
    return None
