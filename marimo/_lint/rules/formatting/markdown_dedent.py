# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import io
import tokenize
from typing import TYPE_CHECKING

from marimo._ast.codegen import format_markdown

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._ast.cell import CellImpl


class MarkdownDedentRule(LintRule):
    """MF007: Markdown strings in mo.md() should be dedented.

    This rule detects markdown strings in `mo.md()` calls that have unnecessary
    leading indentation. Dedenting markdown improves readability and produces
    cleaner diffs in version control.

    ## What it does

    Checks cells containing `mo.md()` calls to see if the markdown string
    content has unnecessary leading whitespace that should be removed.

    ## Why is this bad?

    Indented markdown strings:
    - Are harder to read when viewing the source code
    - Produce larger diffs when making changes
    - Don't match the standard marimo formatting style
    - Can be confusing when the indentation doesn't reflect the markdown structure

    ## Examples

    **Problematic:**
    ```python
    mo.md(
        r\"\"\"
        # Title

        Some content here.
        \"\"\"
    )
    ```

    **Solution:**
    ```python
    mo.md(
        r\"\"\"
    # Title

    Some content here.
    \"\"\"
    )
    ```

    **Note:** This fix is automatically applied with `marimo check --fix`.

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Best Practices](https://docs.marimo.io/guides/best_practices/)
    """

    code = "MF007"
    name = "markdown-dedent"
    description = "Markdown strings in mo.md() should be dedented."
    severity = Severity.FORMATTING
    fixable = True

    async def check(self, ctx: RuleContext) -> None:
        """Check for markdown cells with indented content."""
        graph = ctx.get_graph()

        # Check each cell in the graph
        for _cell_id, cell in graph.cells.items():
            # Only check markdown cells
            print(cell.markdown)
            if cell.markdown is None:
                continue

            # Check if the markdown string needs dedenting
            # Use tokenize like codegen does to extract quote style
            needs_dedent = format_markdown(cell) != cell.code
            if needs_dedent:
                # Find the corresponding notebook cell for position info
                notebook_cell = None
                for nb_cell in ctx.notebook.cells:
                    if nb_cell.code.strip() == cell.code.strip():
                        notebook_cell = nb_cell
                        break

                if notebook_cell:
                    diagnostic = Diagnostic(
                        message="Markdown string should be dedented for better readability",
                        line=notebook_cell.lineno,  # cell start + 1 - 1
                        column=notebook_cell.col_offset + 1,
                    )
                    await ctx.add_diagnostic(diagnostic)
