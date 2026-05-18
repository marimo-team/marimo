# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from marimo._ast.parse import ast_parse
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext

# Functions that trap at runtime even though their parent module imports fine.
UNSAFE_ATTR_CALLS: dict[str, set[str]] = {
    "os": {
        "system",
        "popen",
        "fork",
        "kill",
        "killpg",
        "getuid",
        "getgid",
    },
    "signal": {"signal", "alarm"},
}

# Prefixes for os.exec*, os.spawn* families.
UNSAFE_ATTR_PREFIXES: dict[str, tuple[str, ...]] = {
    "os": ("exec", "spawn"),
}

UNSAFE_BUILTINS = frozenset({"breakpoint"})


class _UnsafeCallVisitor(ast.NodeVisitor):
    """Collect unsafe calls with their line/column info."""

    def __init__(self) -> None:
        self.findings: list[tuple[int, int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Check module.func() calls like os.system()
        if isinstance(node.func, ast.Attribute):
            value = node.func.value
            if isinstance(value, ast.Name):
                module = value.id
                attr = node.func.attr

                # Exact matches
                exact = UNSAFE_ATTR_CALLS.get(module)
                if exact and attr in exact:
                    self.findings.append(
                        (node.lineno, node.col_offset, f"{module}.{attr}()")
                    )

                # Prefix matches (os.execl, os.spawnv, etc.)
                prefixes = UNSAFE_ATTR_PREFIXES.get(module)
                if prefixes and any(attr.startswith(p) for p in prefixes):
                    # Avoid double-reporting if also in exact set
                    if not (exact and attr in exact):
                        self.findings.append(
                            (
                                node.lineno,
                                node.col_offset,
                                f"{module}.{attr}()",
                            )
                        )

        # Check bare builtins like breakpoint()
        elif isinstance(node.func, ast.Name):
            if node.func.id in UNSAFE_BUILTINS:
                self.findings.append(
                    (node.lineno, node.col_offset, f"{node.func.id}()")
                )

        self.generic_visit(node)


class UnsafeSystemCallsRule(LintRule):
    """MW002: System calls that fail in WASM/Pyodide.

    This rule detects calls to OS-level functions that silently fail or
    raise errors in the Pyodide runtime, even though their parent modules
    import successfully.

    ## What it does

    Walks the AST of each cell looking for calls to functions like
    ``os.system()``, ``os.fork()``, ``signal.signal()``, and
    ``breakpoint()`` that have no meaningful implementation in WASM.

    ## Why is this bad?

    These functions depend on OS features (process spawning, signal
    handling, debugger attachment) that don't exist in a browser
    environment. They will raise ``OSError``, ``NotImplementedError``,
    or hang silently.

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
        for cell in ctx.notebook.cells:
            try:
                tree = ast_parse(cell.code)
            except SyntaxError:
                continue

            visitor = _UnsafeCallVisitor()
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
