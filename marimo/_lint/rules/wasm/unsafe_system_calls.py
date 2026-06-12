# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._ast.parse import ast_parse
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.wasm._unsafe_call_analysis import (
    UnsafeCallVisitor,
    record_import_data_alias,
)

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class UnsafeSystemCallsRule(LintRule):
    """MW002: System calls that fail in WASM/Pyodide.

    This rule detects calls to OS-level functions that silently fail or
    raise errors in the Pyodide runtime, even though their parent modules
    import successfully.

    ## What it does

    Walks the AST of each cell looking for calls to functions like
    `os.system()`, `os.fork()`, `signal.signal()`, `multiprocessing.Pipe()`,
    and `breakpoint()` that have no meaningful implementation in WASM.

    ## Why is this bad?

    These functions depend on OS features (process spawning, signal
    handling, debugger attachment, unsupported multiprocessing
    synchronization, or IPC) that don't exist in a browser environment.
    They will raise `OSError`, `NotImplementedError`, or hang silently.

    ## Examples

    **Problematic:**
    ```python
    import os

    os.system("ls")
    ```

    **Problematic:**
    ```python
    breakpoint()
    ```

    **Problematic:**
    ```python
    import multiprocessing

    multiprocessing.Pipe()
    ```

    **Solution:**
    Remove or guard these calls behind a WASM detection check.

    ## References

    - https://pyodide.org/en/stable/usage/wasm-constraints.html
    """

    code = "MW002"
    name = "unsafe-system-call"
    description = "System call that fails in WASM/Pyodide"
    severity = Severity.WASM
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        module_aliases: dict[str, str] = {}
        call_aliases: dict[str, str] = {}
        start_method_aliases: dict[str, str] = {}
        for cell_impl in ctx.get_graph().cells.values():
            for import_data in cell_impl.imports:
                record_import_data_alias(
                    module_aliases,
                    call_aliases,
                    start_method_aliases,
                    import_data,
                )

        alias_collector = UnsafeCallVisitor(
            module_aliases=module_aliases,
            call_aliases=call_aliases,
            start_method_aliases=start_method_aliases,
        )
        for cell in ctx.notebook.cells:
            try:
                tree = ast_parse(cell.code)
            except SyntaxError:
                continue
            alias_collector.visit(tree)
        module_aliases = alias_collector.module_alias_scopes[0]
        call_aliases = alias_collector.call_alias_scopes[0]
        start_method_aliases = alias_collector.start_method_alias_scopes[0]
        bound_names = alias_collector.bound_scopes[0]

        for cell in ctx.notebook.cells:
            try:
                tree = ast_parse(cell.code)
            except SyntaxError:
                continue

            visitor = UnsafeCallVisitor(
                module_aliases=module_aliases,
                call_aliases=call_aliases,
                start_method_aliases=start_method_aliases,
                bound_names=bound_names,
            )
            visitor.visit(tree)

            for lineno, col_offset, call_name in visitor.findings:
                await ctx.add_diagnostic(
                    Diagnostic(
                        message=(
                            f"'{call_name}' is not supported in WASM/Pyodide "
                            "and will fail at runtime."
                        ),
                        line=cell.lineno + lineno - 1,
                        column=cell.col_offset + col_offset,
                        fix=f"Remove or guard '{call_name}' for WASM compatibility.",
                    )
                )
