# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from marimo._ast.parse import ast_parse
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._schemas.serialization import CellDef


class BranchExpressionRule(LintRule):
    """MR002: Branch statements with output expressions that won't be displayed.

    This rule detects when the last statement in a cell is a branch (if/elif/else,
    match, or try/except/finally) containing expressions that produce output. In
    marimo, only the last expression at the top level of a cell is displayed.
    Expressions nested inside branches will execute but not be shown to the user,
    which can be confusing if the user expected to see output.

    ## Why is this bad?

    When output expressions are nested inside branches at the end of a cell:
    - The expressions execute but produce no visible output
    - Users expect to see the result (like mo.md(), string literals, etc.)
    - This can lead to confusion about whether code is running correctly
    - It violates the principle of least surprise

    This is a runtime issue because it causes unexpected behavior where the user's
    intended output is silently ignored.

    ## Examples

    **Problematic:**
    ```python
    if condition:
        mo.md("Result A")  # Won't be displayed
    else:
        mo.md("Result B")  # Won't be displayed
    ```

    **Problematic:**
    ```python
    match value:
        case 1:
            "Too short"  # Won't be displayed
        case _:
            value  # Won't be displayed
    ```

    **Not flagged:**
    ```python
    if condition:
        print("Debug message")  # Function calls
    ```

    **Solution:**
    ```python
    # Assign to a variable that marimo will display
    result = mo.md("Result A") if condition else mo.md("Result B")
    result
    ```

    **Solution:**
    ```python
    # Create a default variable for response.
    result = None
    if condition:
        result = expr
    else:
        result = other
    result
    ```

    **Alternative Solution (if no output intended):**
    ```python
    # Use a dummy variable to indicate intentional suppression
    if condition:
        _ = expr
    else:
        _ = other
    ```

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Reactivity](https://docs.marimo.io/guides/reactivity/)
    """

    code = "MR002"
    name = "branch-expression"
    description = (
        "Branch statements with output expressions that won't be displayed"
    )
    severity = Severity.RUNTIME
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Check for branch statements with trailing expressions."""
        for cell in ctx.notebook.cells:
            # Skip empty cells
            if not cell.code.strip():
                continue

            try:
                tree = ast_parse(cell.code)

                # Check if there are any statements
                if not tree.body:
                    continue

                # Get the last statement
                last_stmt = tree.body[-1]

                # Check if it's a branch statement
                if isinstance(last_stmt, ast.If):
                    await self._check_if_statement(last_stmt, cell, ctx)
                elif isinstance(last_stmt, ast.Match):
                    await self._check_match_statement(last_stmt, cell, ctx)
                elif isinstance(last_stmt, ast.Try):
                    await self._check_try_statement(last_stmt, cell, ctx)

            except SyntaxError:
                # Skip cells that don't parse
                continue

    async def _check_if_statement(
        self, node: ast.If, cell: CellDef, ctx: RuleContext
    ) -> None:
        """Check if an if statement has branches with output expressions."""
        branches = self._collect_if_branches(node)

        # Check if ANY branch has an output expression
        if not branches:
            return

        if any(self._has_output_expression(branch) for branch in branches):
            await self._report_diagnostic(node, cell, ctx, "if statement")

    async def _check_match_statement(
        self, node: ast.Match, cell: CellDef, ctx: RuleContext
    ) -> None:
        """Check if a match statement has cases with output expressions."""
        if not node.cases:
            return

        branches = [case.body for case in node.cases]

        # Check if ANY case has an output expression
        if any(self._has_output_expression(branch) for branch in branches):
            await self._report_diagnostic(node, cell, ctx, "match statement")

    async def _check_try_statement(
        self, node: ast.Try, cell: CellDef, ctx: RuleContext
    ) -> None:
        """Check if a try statement has branches with output expressions."""
        branches = [node.body]

        # Add exception handlers
        for handler in node.handlers:
            branches.append(handler.body)

        # Add else clause if present
        if node.orelse:
            branches.append(node.orelse)

        # Add finally clause if present
        if node.finalbody:
            branches.append(node.finalbody)

        # Check if ANY branch has an output expression
        if any(self._has_output_expression(branch) for branch in branches):
            await self._report_diagnostic(node, cell, ctx, "try statement")

    def _collect_if_branches(self, node: ast.If) -> list[list[ast.stmt]]:
        """Collect all branches from an if/elif/else statement."""
        branches = [node.body]

        # Process orelse (could be elif or else)
        current = node
        while current.orelse:
            if len(current.orelse) == 1 and isinstance(
                current.orelse[0], ast.If
            ):
                # This is an elif
                current = current.orelse[0]
                branches.append(current.body)
            else:
                # This is an else
                branches.append(current.orelse)
                break

        return branches

    def _has_output_expression(self, stmts: list[ast.stmt]) -> bool:
        """Check if a branch has a trailing value expression.

        Returns True for expressions that produce values:
        - Constants: 42, "string", True, None
        - Names: x, obj, slider
        - Attributes: obj.attr, slider.value
        - Operations: a + b, a == b, not x
        - Marimo output calls: mo.md(), mo.ui.button()

        Returns False for:
        - All function calls (assumed side effects): func(), obj.method()
        - Except marimo output calls which ARE flagged
        """
        if not stmts:
            return False

        last_stmt = stmts[-1]
        if not isinstance(last_stmt, ast.Expr):
            return False

        expr = last_stmt.value

        # For calls, only flag marimo output calls
        if isinstance(expr, ast.Call):
            func = expr.func

            # Marimo output calls should be flagged (mo.md, mo.ui.*, etc.)
            return self._is_marimo_output_call(func)

        # All other expressions (constants, names, attributes, operations) are flagged
        return True

    def _is_marimo_output_call(self, func: ast.expr) -> bool:
        """Check if a call is a marimo output function (mo.md, mo.ui.*, etc.).

        Excludes control flow and side-effect calls like mo.stop() and mo.output.*.
        """
        if isinstance(func, ast.Attribute):
            # Direct mo.* calls (mo.md, mo.Html, etc.)
            if isinstance(func.value, ast.Name) and func.value.id == "mo":
                # Exclude mo.stop()
                if func.attr == "stop":
                    return False
                return True

            # mo.ui.* or other nested mo.* calls
            if isinstance(func.value, ast.Attribute):
                if (
                    isinstance(func.value.value, ast.Name)
                    and func.value.value.id == "mo"
                ):
                    # Exclude mo.output.* calls (append, replace, clear)
                    if func.value.attr == "output":
                        return False
                    return True

        return False

    async def _report_diagnostic(
        self, node: ast.stmt, cell: CellDef, ctx: RuleContext, stmt_type: str
    ) -> None:
        """Report a diagnostic for a branch with trailing expressions."""
        message = (
            f"The {stmt_type} has branches ending with expressions that won't be displayed. "
            "marimo can only display the last expression if it is unnested. "
            "If this was intentional, consider assigning to a dummy variable: `_ = ...`"
        )

        diagnostic = Diagnostic(
            message=message,
            line=cell.lineno + node.lineno - 1,
            column=node.col_offset + 1,
        )

        await ctx.add_diagnostic(diagnostic)
