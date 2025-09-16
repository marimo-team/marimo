# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class StdoutRule(LintRule):
    """MF002: Parse captured stdout during notebook loading.

    This rule processes any output that was captured from stdout while marimo
    was parsing and loading a notebook file. Stdout output during parsing
    typically indicates warnings or informational messages from the Python
    interpreter or imported modules.

    ## What it does

    Captures and parses stdout output during notebook loading, looking for
    structured warning messages that include file and line number references.
    Creates diagnostics from any warnings or messages found.

    ## Why is this bad?

    While stdout output doesn't prevent execution, it often indicates:
    - Deprecation warnings from imported libraries
    - Configuration issues
    - Potential compatibility problems
    - Code that produces unexpected side effects during import

    ## Examples

    **Captured stdout:**
    ```
    notebook.py:15: DeprecationWarning: 'imp' module is deprecated
    ```

    **Result:** Creates a diagnostic pointing to line 15 with the deprecation warning.

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    """

    code = "MF002"
    name = "parse-stdout"
    description = "Parse captured stdout during notebook loading"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Process captured stdout and create diagnostics."""
        # Pattern to match file:line format (e.g., "file.py:68: SyntaxWarning")
        line_pattern = re.compile(r"([^:]+):(\d+):\s*(.+)")

        # Split stderr by lines to handle multiple warnings
        lines = ctx.stdout.strip().split("\n")
        captured = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this line contains a file:line reference
            match = line_pattern.match(line)
            if match:
                captured = True
                _, line_num_str, warning_msg = match.groups()
                await ctx.add_diagnostic(
                    Diagnostic(
                        message=warning_msg,
                        line=int(line_num_str) - 1,  # Convert to 0-based index
                        cell_id=None,
                        column=0,
                    )
                )

        # Fallback: if no line patterns found, create single diagnostic
        if not captured and ctx.stdout:
            await ctx.add_diagnostic(
                Diagnostic(
                    message=f"Parsing warning: {ctx.stderr}",
                    cell_id=None,
                    line=0,
                    column=0,
                )
            )


class StderrRule(LintRule):
    """MF003: Parse captured stderr during notebook loading.

    This rule processes any output that was captured from stderr while marimo
    was parsing and loading a notebook file. Stderr output typically contains
    warnings and error messages from the Python interpreter, such as syntax
    warnings, deprecation notices, and import errors.

    ## What it does

    Captures stderr output during notebook loading and creates diagnostics
    from any error messages or warnings. This helps identify potential
    issues that don't prevent parsing but may affect runtime behavior.

    ## Why is this bad?

    Stderr output during parsing often indicates:
    - Syntax warnings (like invalid escape sequences)
    - Import warnings or errors
    - Deprecation notices from libraries
    - Configuration issues that might affect execution

    While these don't break the notebook, they can lead to unexpected
    behavior or indicate code that needs updating.

    ## Examples

    **Captured stderr:**
    ```
    notebook.py:68: SyntaxWarning: invalid escape sequence '\\l'
    ```

    **Result:** Creates a diagnostic pointing to line 68 about the invalid escape sequence.

    **Common issues:**
    - Raw strings needed: `r"\\path\to\file"` instead of `"\\path\to\file"`
    - Deprecated library usage
    - Missing import dependencies

    ## References

    - [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
    - [Python Warning Categories](https://docs.python.org/3/library/warnings.html#warning-categories)
    """

    code = "MF003"
    name = "parse-stderr"
    description = "Parse captured stderr during notebook loading"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        # Process stderr content
        if ctx.stderr:
            await ctx.add_diagnostic(
                Diagnostic(
                    message=f"stderr: {ctx.stderr}",
                    cell_id=None,
                    line=0,
                    column=0,
                )
            )
