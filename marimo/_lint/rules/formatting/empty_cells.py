# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from marimo._ast.parse import ast_parse
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import UnsafeFixRule
from marimo._schemas.serialization import NotebookSerialization
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class EmptyCellRule(UnsafeFixRule):
    """MF004: Empty cells that can be safely removed.

    This rule identifies cells that contain only whitespace, comments, or `pass`
    statements and can be safely removed from the notebook without affecting
    functionality. Empty cells often accumulate during development and can
    clutter the notebook structure.

    ## What it does

    Detects cells that contain only:
    - Whitespace characters (spaces, tabs, newlines)
    - Comments (lines starting with #)
    - Pass statements (`pass`)
    - Any combination of the above

    ## Why is this bad?

    Empty cells can:
    - Create clutter in notebook structure
    - Add unnecessary complexity to the execution graph
    - Make notebooks harder to read and maintain
    - Increase file size without adding value

    While not functionally breaking, removing empty cells improves code
    clarity and reduces visual noise.

    ## Examples

    **Problematic:**
    ```python
    # Cell 1: Only whitespace
    ```

    **Problematic:**
    ```python
    # Cell 2: Only comments
    # This is just a comment
    # Nothing else here
    ```

    **Problematic:**
    ```python
    # Cell 3: Only pass statement
    pass
    ```

    **Problematic:**
    ```python
    # Cell 4: Mix of comments, whitespace, and pass
    # Some comment

    pass
    # Another comment
    ```

    **Note:** This fix requires `--unsafe-fixes` because removing cells changes
    the notebook structure, and potentially removes user-intended content.

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Best Practices](https://docs.marimo.io/guides/best_practices/)
    """

    code = "MF004"
    name = "empty-cells"
    description = "Empty cells that can be safely removed."
    severity = Severity.FORMATTING
    fixable = "unsafe"

    async def check(self, ctx: RuleContext) -> None:
        """Check for empty cells that can be removed."""
        for i, cell in enumerate(ctx.notebook.cells):
            if self._is_empty_cell(cell.code):
                # Create diagnostic for this empty cell
                idx = CellId_t(str(i))
                diagnostic = Diagnostic(
                    message="Empty cell can be removed (contains only whitespace, comments, or pass)",
                    cell_id=[idx],
                    line=cell.lineno - 1,  # Convert 1-based to 0-based
                    column=cell.col_offset,
                    fixable="unsafe",
                )

                await ctx.add_diagnostic(diagnostic)

    def apply_unsafe_fix(
        self, notebook: NotebookSerialization, diagnostics: list[Diagnostic]
    ) -> NotebookSerialization:
        """Remove empty cells from the notebook.

        Args:
            notebook: The notebook to modify
            diagnostics: List of diagnostics containing cell information

        Returns:
            Modified notebook with empty cells removed
        """
        # Collect all cell IDs to remove from all diagnostics
        cells_to_remove: set[CellId_t] = set()
        for diagnostic in diagnostics:
            if diagnostic.cell_id is not None:
                (cell_id,) = diagnostic.cell_id
                cells_to_remove.add(cell_id)

        # Remove cells with matching IDs
        cells = [
            cell
            for i, cell in enumerate(notebook.cells)
            if CellId_t(str(i)) not in cells_to_remove
        ]
        return NotebookSerialization(
            header=notebook.header,
            version=notebook.version,
            app=notebook.app,
            cells=cells,
            violations=notebook.violations,
            valid=notebook.valid,
            filename=notebook.filename,
        )

    def _is_empty_cell(self, code: str) -> bool:
        """Check if a cell is considered empty.

        Args:
            code: The cell's source code

        Returns:
            True if the cell is empty (contains only whitespace, comments, or pass)
        """
        # Strip whitespace
        stripped = code.strip()

        # Empty after stripping whitespace
        if not stripped:
            return True

        try:
            # Parse the code to check what statements it contains
            tree = ast_parse(stripped)

            # If no statements, it's empty
            if not tree.body:
                return True

            # Check if all statements are pass statements
            for node in tree.body:
                if not isinstance(node, ast.Pass):
                    return False

            return True

        except SyntaxError:
            # If it doesn't parse, check if it's only comments
            return self._is_only_comments(code)

    def _is_only_comments(self, code: str) -> bool:
        """Check if code contains only comments and whitespace.

        Args:
            code: The source code to check

        Returns:
            True if the code contains only comments and whitespace
        """
        lines = code.splitlines()

        for line in lines:
            stripped_line = line.strip()
            # Skip empty lines
            if not stripped_line:
                continue
            # If line doesn't start with #, it's not just a comment
            if not stripped_line.startswith("#"):
                return False

        return True
