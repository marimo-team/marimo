# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.breaking.graph import GraphRule

if TYPE_CHECKING:
    from marimo._ast.visitor import ImportData
    from marimo._lint.context import RuleContext
    from marimo._runtime.dataflow import DirectedGraph

# Stdlib modules that don't exist or are non-functional stubs in Pyodide.
INCOMPATIBLE_MODULES = frozenset(
    {
        "subprocess",
        "pdb",
        "dbm",
        "resource",
        "fcntl",
        "termios",
        "readline",
        "curses",
        "tkinter",
        # Removed entirely from the distribution as of Pyodide 314.0.0.
        "pydecimal",
        "test",
    }
)

UNSUPPORTED_MULTIPROCESSING_TOP_LEVEL_EXPORTS = frozenset(
    {
        "Array",
        "Barrier",
        "BoundedSemaphore",
        "Condition",
        "Event",
        "JoinableQueue",
        "Lock",
        "Manager",
        "Pipe",
        "RLock",
        "RawArray",
        "RawValue",
        "Semaphore",
        "Value",
        "connection",
        "forkserver",
        "heap",
        "managers",
        "shared_memory",
        "sharedctypes",
        "synchronize",
    }
)

UNSUPPORTED_MULTIPROCESSING_EXPORTS_BY_MODULE = {
    "multiprocessing": UNSUPPORTED_MULTIPROCESSING_TOP_LEVEL_EXPORTS,
    "multiprocessing.context": frozenset(
        {
            "ForkContext",
            "ForkProcess",
            "ForkServerContext",
            "ForkServerProcess",
        }
    ),
    "multiprocessing.pool": frozenset({"ThreadPool"}),
    "multiprocessing.queues": frozenset({"JoinableQueue"}),
}

UNSUPPORTED_MULTIPROCESSING_SUBMODULES = frozenset(
    f"multiprocessing.{name}"
    for name in UNSUPPORTED_MULTIPROCESSING_TOP_LEVEL_EXPORTS
    if name.islower()
)


def _unsupported_multiprocessing_import(
    import_data: ImportData,
) -> str | None:
    if import_data.import_level not in (None, 0):
        return None

    unsupported_exports = UNSUPPORTED_MULTIPROCESSING_EXPORTS_BY_MODULE.get(
        import_data.module
    )
    imported_symbol = import_data.imported_symbol
    if unsupported_exports is not None and imported_symbol is not None:
        prefix = f"{import_data.module}."
        if imported_symbol.startswith(prefix):
            top_level_import = imported_symbol.removeprefix(prefix).split(
                ".",
                maxsplit=1,
            )[0]
            if top_level_import in unsupported_exports:
                return imported_symbol

    if import_data.module in UNSUPPORTED_MULTIPROCESSING_SUBMODULES:
        return import_data.module

    return None


class IncompatibleImportsRule(GraphRule):
    """MW001: Importing modules unavailable in WASM/Pyodide.

    This rule detects imports of standard library modules and
    multiprocessing APIs that are missing or non-functional in the
    Pyodide runtime used by WASM notebooks.

    ## What it does

    Checks each cell's imports against stdlib modules that don't work in
    Pyodide, plus multiprocessing exports and submodules that require
    shared memory, managers, pipes, or native synchronization.

    ## Why is this bad?

    WASM notebooks run in the browser via Pyodide, which cannot support
    modules that depend on OS-level process control, terminal I/O, native
    GUI toolkits, shared memory, pipes, or native synchronization. These
    imports can raise ImportError or fail at runtime. WASM-compatible
    multiprocessing adapters such as `Process`, `Queue`, `SimpleQueue`,
    `Pool`, and `ProcessPoolExecutor` remain allowed.

    ## Examples

    **Problematic:**
    ```python
    import subprocess

    result = subprocess.run(["ls"])
    ```

    **Problematic:**
    ```python
    from multiprocessing import Pipe
    ```

    **Solution:**
    Remove the import or replace it with a WASM-compatible alternative.

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
                    line, column = self._get_variable_line_info(
                        cell_id, variable, ctx
                    )
                    if top_level in INCOMPATIBLE_MODULES:
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
                        continue

                    multiprocessing_import = (
                        _unsupported_multiprocessing_import(
                            var_data.import_data
                        )
                    )
                    if multiprocessing_import is not None:
                        await ctx.add_diagnostic(
                            Diagnostic(
                                message=(
                                    f"Multiprocessing API '{multiprocessing_import}' "
                                    "is not supported in WASM/Pyodide."
                                ),
                                line=line,
                                column=column,
                                fix=(
                                    f"Remove or replace '{multiprocessing_import}' "
                                    "with a WASM-compatible multiprocessing adapter."
                                ),
                            )
                        )
