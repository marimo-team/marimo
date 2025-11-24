# Copyright 2025 Marimo. All rights reserved.
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
    """MR002: Branch statements ending with expressions that won't be displayed.

    This rule detects when the last statement in a cell is a branch (if/elif/else,
    match, or try/except/finally) where all branches end with expressions. In marimo,
    only the last expression at the top level of a cell is displayed. Expressions
    nested inside branches will execute but not be shown to the user, which can be
    confusing if the user expected to see output.

    ## Why is this bad?

    When expressions are nested inside branches at the end of a cell:
    - The expressions execute but produce no visible output
    - Users may expect to see the result (like `mo.md()` calls) but won't
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
            "Just right"  # Won't be displayed
    ```

    **Problematic:**
    ```python
    if invalid:
        mo.md("Error message")  # Won't be displayed even without else clause
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
        result = expr()
    else:
        result = other()
    result
    ```

    In the case where no output is expected:

    **Alternative Solution:**
    ```python
    # Use a dummy variable to indicate intentional suppression
    if condition:
        _ = print("Result A")
    else:
        _ = print("Result B")
    ```

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Reactivity](https://docs.marimo.io/guides/reactivity/)
    """

    code = "MR002"
    name = "branch-expression"
    description = (
        "Branch statements with trailing expressions that won't be displayed"
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
        """Check if an if statement has all branches ending with expressions."""
        branches = self._collect_if_branches(node)

        # Check if ALL branches end with expressions
        if not branches:
            return

        if all(self._ends_with_expression(branch) for branch in branches):
            await self._report_diagnostic(node, cell, ctx, "if statement")

    async def _check_match_statement(
        self, node: ast.Match, cell: CellDef, ctx: RuleContext
    ) -> None:
        """Check if a match statement has all cases ending with expressions."""
        if not node.cases:
            return

        branches = [case.body for case in node.cases]

        # Check if ALL cases end with expressions
        if all(self._ends_with_expression(branch) for branch in branches):
            await self._report_diagnostic(node, cell, ctx, "match statement")

    async def _check_try_statement(
        self, node: ast.Try, cell: CellDef, ctx: RuleContext
    ) -> None:
        """Check if a try statement has all branches ending with expressions."""
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

        # Check if ALL branches end with expressions
        if all(self._ends_with_expression(branch) for branch in branches):
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

    def _ends_with_expression(self, stmts: list[ast.stmt]) -> bool:
        """Check if a list of statements ends with an expression statement."""
        if not stmts:
            return False

        last_stmt = stmts[-1]
        return isinstance(last_stmt, ast.Expr)

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
