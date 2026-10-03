# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from marimo._ast.names import SETUP_CELL_NAME
from marimo._ast.parse import ast_parse
from marimo._ast.variables import is_local
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class MixedImportsRule(LintRule):
    """MR005: Imports mixed with literal configuration assignments.

    ## What it does

    Detects cells containing imports and assignments of literal values to
    simple names. Setup cells, cells containing other statements and cells
    whose assignments depend on imported names are excluded.

    ## Why is this bad?

    marimo handles import-only cells incrementally: adding a new import does
    not rerun cells that depend on unchanged imports. Adding a configuration
    assignment to the same cell disables this optimization. Editing that cell
    can then rerun expensive computations that depend on its imports, even
    when those imports have not changed.

    Keep imports in their own cell and configuration in a separate cell to
    preserve incremental imports. No automatic fix is provided because
    splitting cells changes when their code runs. If grouping the statements
    is intentional, ignore `MR005` in your lint configuration.

    ## Examples

    **Problematic:**
    ```python
    import math

    THRESHOLD = 10
    ```

    **Solution:**
    ```python
    # One cell
    import math
    ```

    ```python
    # Another cell
    THRESHOLD = 10
    ```

    ## References

    - [Reactivity](https://docs.marimo.io/guides/reactivity/)
    """

    code = "MR005"
    name = "mixed-imports"
    description = "Imports mixed with literal configuration assignments"
    severity = Severity.RUNTIME
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        for cell in ctx.notebook.cells:
            if cell.name == SETUP_CELL_NAME:
                continue

            try:
                tree = ast_parse(cell.code)
            except SyntaxError:
                continue

            imports = [
                node
                for node in tree.body
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            assignments = [
                node
                for node in tree.body
                if not isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            imported_names = {
                alias.asname or alias.name.split(".")[0]
                for node in imports
                if not (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "__future__"
                )
                for alias in node.names
            }
            if (
                not assignments
                or "*" in imported_names
                or not any(not is_local(name) for name in imported_names)
                or not all(
                    self._is_configuration(node, imported_names)
                    for node in assignments
                )
            ):
                continue

            first = assignments[0]
            await ctx.add_diagnostic(
                Diagnostic(
                    message="Mixing imports with configuration disables incremental imports.",
                    line=cell.lineno + first.lineno - 1,
                    column=cell.col_offset + first.col_offset + 1,
                    fix=(
                        "Move the configuration assignments into a separate cell. "
                        "Adding imports to an import-only cell does not rerun "
                        "cells that depend on unchanged imports."
                    ),
                )
            )

    @staticmethod
    def _is_configuration(node: ast.stmt, imported_names: set[str]) -> bool:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            return False

        if isinstance(node, ast.Assign):
            targets = node.targets
        else:
            targets = [node.target]
            if any(
                isinstance(part, ast.Name) and part.id in imported_names
                for part in ast.walk(node.annotation)
            ):
                return False
        if any(
            not isinstance(target, ast.Name) or target.id in imported_names
            for target in targets
        ):
            return False

        # Keep initialization that uses imports or calls together.
        if node.value is None or any(
            isinstance(part, ast.Call) for part in ast.walk(node.value)
        ):
            return False
        try:
            ast.literal_eval(node.value)
        except (ValueError, TypeError):
            return False
        return True
