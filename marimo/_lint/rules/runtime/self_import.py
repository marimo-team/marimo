# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.breaking.graph import GraphRule
from marimo._utils.site_packages import (
    has_local_conflict,
)

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._runtime.dataflow import DirectedGraph


class SelfImportRule(GraphRule):
    """MR001: Importing a module with the same name as the file.

    This rule detects attempts to import a module that has the same name as the
    current file. This can cause import conflicts, circular import issues, and
    unexpected behavior where the file might try to import itself instead of
    the intended external module.

    ## What it does

    Analyzes import statements in each cell to detect cases where the imported
    module name matches the current file's name (without the .py extension).

    ## Why is this bad?

    Importing a module with the same name as the file causes several issues:
    - Python may attempt to import the current file instead of the intended module
    - This can lead to circular import errors or unexpected behavior
    - It makes the code confusing and hard to debug
    - It can prevent the notebook from running correctly

    This is a runtime issue because it can cause import confusion and unexpected behavior.

    ## Examples

    **Problematic (in a file named `requests.py`):**
    ```python
    import requests  # Error: conflicts with file name
    ```

    **Problematic (in a file named `math.py`):**
    ```python
    from math import sqrt  # Error: conflicts with file name
    ```

    **Solution:**
    ```python
    # Rename the file to something else, like my_requests.py
    import requests  # Now this works correctly
    ```

    **Alternative Solution:**
    ```python
    # Use a different approach that doesn't conflict
    import urllib.request  # Use alternative library
    ```

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Python Import System](https://docs.python.org/3/reference/import.html)
    """

    code = "MR001"
    name = "self-import"
    description = "Importing a module with the same name as the file"
    severity = Severity.RUNTIME
    fixable = False

    async def _validate_graph(
        self, graph: DirectedGraph, ctx: RuleContext
    ) -> None:
        """Check for imports that conflict with the file name."""
        # Get the file name without extension
        if not ctx.notebook.filename:
            return

        file_name = os.path.basename(ctx.notebook.filename)
        if file_name.endswith(".py"):
            module_name = file_name[:-3]
        else:
            # For .md or other extensions, we can't determine conflicts
            return

        # Get directory containing the notebook file for local package checking
        notebook_dir = os.path.dirname(ctx.notebook.filename)

        await self._check_cells_for_conflicts(
            graph, ctx, module_name, file_name, notebook_dir
        )

    async def _check_cells_for_conflicts(
        self,
        graph: DirectedGraph,
        ctx: RuleContext,
        module_name: str,
        file_name: str,
        notebook_dir: str,
    ) -> None:
        """Check all cells for import conflicts using compiled cell data."""
        for cell_id, cell_impl in graph.cells.items():
            # Check imports from compiled cell data
            for variable, var_data_list in cell_impl.variable_data.items():
                for var_data in var_data_list:
                    if var_data.import_data is None:
                        continue

                    import_data = var_data.import_data
                    top_level_module = import_data.module.split(".")[0]
                    fix_msg = f"Rename the file to avoid conflicts with the '{top_level_module}' module. "
                    if top_level_module == module_name:
                        # Standard self-import conflict
                        message = f"Importing module '{top_level_module}' conflicts with file name '{file_name}'"
                    # Check if there's a local file/package with the same name
                    elif has_local_conflict(top_level_module, notebook_dir):
                        # Module exists in site-packages - enhanced diagnostic
                        message = (
                            f"Importing module '{top_level_module}' conflicts "
                            "with a module in site-packages, and may cause import ambiguity."
                        )
                    else:
                        continue

                    line, column = self._get_variable_line_info(
                        cell_id, variable, ctx
                    )
                    diagnostic = Diagnostic(
                        message=message,
                        line=line,
                        column=column,
                        code=self.code,
                        name=self.name,
                        severity=self.severity,
                        fixable=self.fixable,
                        fix=fix_msg,
                    )
                    await ctx.add_diagnostic(diagnostic)
