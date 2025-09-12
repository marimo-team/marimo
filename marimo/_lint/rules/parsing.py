# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule

if TYPE_CHECKING:
    from marimo._lint.context import RuleContext


class ParseDiagnosticsRule(LintRule):
    """MF002/MF003: Parse stdout/stderr captured during notebook loading.

    When marimo parses a notebook file, any output to stdout or stderr
    (such as syntax warnings) is captured and converted to formatting
    diagnostics. This rule processes that captured output and extracts
    useful information like line numbers.

    Examples:
        Stderr: "file.py:68: SyntaxWarning: invalid escape sequence '\\l'"
        -> Creates diagnostic pointing to line 68

        Stdout: General parsing information
        -> Creates diagnostic at line 1
    """

    code = "MF002"  # Will be overridden per diagnostic type
    name = "parse-diagnostics"
    description = "Parse captured stdout/stderr during notebook loading"
    severity = Severity.FORMATTING
    fixable = False

    def __init__(self, stdout_content: str = "", stderr_content: str = ""):
        """Initialize with captured stdout/stderr content."""
        self.stdout_content = stdout_content.strip()
        self.stderr_content = stderr_content.strip()

    async def check(self, ctx: RuleContext) -> None:
        """Process captured stdout/stderr and create diagnostics."""
        filename = getattr(ctx.notebook, 'filename', '<marimo>')

        # Process stdout content
        if self.stdout_content:
            await ctx.add_diagnostic(
                Diagnostic(
                    message=f"Parsing output: {self.stdout_content}",
                    cell_id=None,
                    line=1,
                    column=1,
                    code="MF002",
                    name="parsing-output",
                    severity=Severity.FORMATTING,
                    fixable=False,
                    filename=filename,
                )
            )

        # Process stderr content - extract line numbers if possible
        if self.stderr_content:
            diagnostics = self._parse_stderr_content(self.stderr_content, filename)
            for diagnostic in diagnostics:
                await ctx.add_diagnostic(diagnostic)

    def _parse_stderr_content(self, stderr_content: str, filename: str) -> list[Diagnostic]:
        """Parse stderr content and extract line numbers where possible."""
        diagnostics = []

        # Pattern to match file:line format (e.g., "file.py:68: SyntaxWarning")
        line_pattern = re.compile(r'([^:]+):(\d+):\s*(.+)')

        # Split stderr by lines to handle multiple warnings
        lines = stderr_content.strip().split('\n')
        current_diagnostic_lines = []
        current_line_num = 1
        current_column = 1

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this line contains a file:line reference
            match = line_pattern.match(line)
            if match:
                # Found a new diagnostic with line number
                if current_diagnostic_lines:
                    # Finish previous diagnostic
                    message = '\n'.join(current_diagnostic_lines)
                    diagnostics.append(
                        Diagnostic(
                            message=f"Parsing warning: {message}",
                            cell_id=None,
                            line=current_line_num,
                            column=current_column,
                            code="MF003",
                            name="parsing-warning",
                            severity=Severity.FORMATTING,
                            fixable=False,
                            filename=filename,
                        )
                    )

                # Start new diagnostic
                file_ref, line_num_str, warning_msg = match.groups()
                current_line_num = int(line_num_str)
                current_column = 1
                current_diagnostic_lines = [line]
            else:
                # Continuation of current diagnostic
                current_diagnostic_lines.append(line)

        # Add final diagnostic if any
        if current_diagnostic_lines:
            message = '\n'.join(current_diagnostic_lines)
            diagnostics.append(
                Diagnostic(
                    message=f"Parsing warning: {message}",
                    cell_id=None,
                    line=current_line_num,
                    column=current_column,
                    code="MF003",
                    name="parsing-warning",
                    severity=Severity.FORMATTING,
                    fixable=False,
                    filename=filename,
                )
            )

        # Fallback: if no line patterns found, create single diagnostic
        if not diagnostics and stderr_content:
            diagnostics.append(
                Diagnostic(
                    message=f"Parsing warning: {stderr_content}",
                    cell_id=None,
                    line=1,
                    column=1,
                    code="MF003",
                    name="parsing-warning",
                    severity=Severity.FORMATTING,
                    fixable=False,
                    filename=filename,
                )
            )

        return diagnostics
