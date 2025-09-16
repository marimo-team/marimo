# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._ast.compiler import (
    ir_cell_factory,
)
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule
from marimo._schemas.serialization import UnparsableCell
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


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
        for cell in ctx.notebook.cells:
            if not isinstance(cell, UnparsableCell):
                try:
                    ir_cell_factory(
                        cell,
                        cell_id=CellId_t("Hbol"),
                        filename=ctx.notebook.filename,
                    )
                except SyntaxError as e:
                    message = f"{e.msg}"
                    await ctx.add_diagnostic(
                        Diagnostic(
                            message=message,
                            line=cell.lineno + (e.lineno or 1) - 1,
                            column=(e.offset or 1),
                            fix=_get_known_hints(message),
                        )
                    )


def _get_known_hints(message: str) -> str | None:
    if message == "'return' outside function":
        return (
            "marimo cells are not normal Python functions; treat cell bodies"
            " as top-level code, or use `@app.function` to define a pure function."
        )
    return None
