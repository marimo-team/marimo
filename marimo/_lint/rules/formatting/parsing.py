# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class StdoutRule(LintRule):
    """MF002: Parse stdout captured during notebook loading.

    When marimo parses a notebook file, any output to stdout.
    """

    code = "MF002"
    name = "parse-stdout"
    description = "Parse captured stdout during notebook loading"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        """Process captured stdout and create diagnostics."""
        # Process stdout content
        if ctx.stdout:
            await ctx.add_diagnostic(
                Diagnostic(
                    message=f"Parsing output: {ctx.stdout}",
                    cell_id=None,
                    line=0,
                    column=0,
                )
            )


class StderrRule(LintRule):
    """MF002: Parse stdout captured during notebook loading.

    When marimo parses a notebook file, any output to stderr (such as syntax
    warnings) is captured and converted to formatting diagnostics. This rule
    processes that captured output and extracts useful information like line
    numbers.

    Examples:
        Stderr: "file.py:68: SyntaxWarning: invalid escape sequence '\\l'"
        -> Creates diagnostic pointing to line 68

        Stdout: General parsing information
        -> Creates diagnostic at line 1
    """

    code = "MF003"
    name = "parse-stderr"
    description = "Parse captured stdout during notebook loading"
    severity = Severity.FORMATTING
    fixable = False

    async def check(self, ctx: RuleContext) -> None:
        # Pattern to match file:line format (e.g., "file.py:68: SyntaxWarning")
        line_pattern = re.compile(r"([^:]+):(\d+):\s*(.+)")

        # Split stderr by lines to handle multiple warnings
        lines = ctx.stderr.strip().split("\n")
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
                        line=int(line_num_str),
                        cell_id=None,
                        column=0,
                    )
                )

        # Fallback: if no line patterns found, create single diagnostic
        if not captured and ctx.stderr:
            await ctx.add_diagnostic(
                Diagnostic(
                    message=f"Parsing warning: {ctx.stderr}",
                    cell_id=None,
                    line=1,
                    column=0,
                )
            )
