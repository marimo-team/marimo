# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.breaking.graph import GraphRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext
    from marimo._runtime.dataflow import DirectedGraph

# Stdlib modules that don't exist or are non-functional stubs in Pyodide.
INCOMPATIBLE_MODULES = frozenset(
    {
        "subprocess",
        "multiprocessing",
        "pdb",
        "dbm",
        "resource",
        "fcntl",
        "termios",
        "readline",
        "curses",
        "tkinter",
        "pydecimal",
        "test",
    }
)


class IncompatibleImportsRule(GraphRule):
    """MW001: Importing modules unavailable in WASM/Pyodide.

    This rule detects imports of standard library modules that are missing
    or non-functional in the Pyodide runtime used by WASM notebooks.

    ## What it does

    Checks each cell's imports against a blocklist of stdlib modules that
    either don't exist in Pyodide or are stubs that fail at runtime.

    ## Why is this bad?

    WASM notebooks run in the browser via Pyodide, which cannot support
    modules that depend on OS-level process control, terminal I/O, or
    native GUI toolkits. Importing these modules will raise ImportError
    or produce broken stubs.

    ## Examples

    **Problematic:**
    ```python
    import subprocess

    result = subprocess.run(["ls"])
    ```

    **Problematic:**
    ```python
    from multiprocessing import Pool
    ```

    **Solution:**
    Remove or replace the import with a WASM-compatible alternative.

    ## References

    - https://pyodide.org/en/stable/usage/wasm-constraints.html
    """

    code = "MW001"
    name = "incompatible-import"
    description = "Importing a module unavailable in WASM/Pyodide"
    severity = Severity.WASM
    fixable = False

    async def _validate_graph(
        self, graph: DirectedGraph, ctx: RuleContext
    ) -> None:
        for cell_id, cell_impl in graph.cells.items():
            for variable, var_data_list in cell_impl.variable_data.items():
                for var_data in var_data_list:
                    if var_data.import_data is None:
                        continue

                    top_level = var_data.import_data.module.split(".")[0]
                    if top_level not in INCOMPATIBLE_MODULES:
                        continue

                    line, column = self._get_variable_line_info(
                        cell_id, variable, ctx
                    )
                    await ctx.add_diagnostic(
                        Diagnostic(
                            message=(
                                f"Module '{top_level}' is not fully "
                                "supported in WASM/Pyodide and will fail "
                                "at import or runtime."
                            ),
                            line=line,
                            column=column,
                            fix=f"Remove or replace '{top_level}' with a WASM-compatible alternative.",
                        )
                    )
