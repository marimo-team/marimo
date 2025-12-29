# Copyright 2026 Marimo. All rights reserved.
"""Full formatter for rich terminal output."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from marimo._cli.print import bold, cyan, light_blue, red, yellow
from marimo._lint.diagnostic import Severity
from marimo._lint.formatters.base import DiagnosticFormatter

if TYPE_CHECKING:
    from marimo._lint.diagnostic import Diagnostic


class FullFormatter(DiagnosticFormatter):
    """Full formatter that shows diagnostics with code context and colors."""

    def format(
        self,
        diagnostic: Diagnostic,
        filename: str,
        code_lines: list[str] | None = None,
    ) -> str:
        """Format the diagnostic for display with code context."""

        # Implementation error if this is raised.
        assert diagnostic.name is not None, diagnostic
        assert diagnostic.severity is not None, diagnostic

        severity_color = {
            Severity.FORMATTING: yellow,
            Severity.RUNTIME: red,
            Severity.BREAKING: red,
        }.get(diagnostic.severity, bold)
        severity_str = {
            Severity.FORMATTING: "warning",
            Severity.RUNTIME: "error",
            Severity.BREAKING: "critical",
        }.get(diagnostic.severity, "info")

        lines, columns = diagnostic.sorted_lines

        location = filename
        if max(lines + (0,)) > 0:
            location = f"{filename}:{lines[0]}:{columns[0]}"

        header = f"{bold(severity_color(severity_str + '[' + diagnostic.name + ']'))}: {bold(diagnostic.message)}"
        header += "\n" + cyan(" --> ") + cyan(location)

        # If code_lines is None, try to read from file
        if code_lines is None and diagnostic.line and os.path.exists(filename):
            try:
                with open(filename, encoding="utf-8") as f:
                    code_lines = f.read().splitlines()
            except (OSError, UnicodeDecodeError):
                # If we can't read the file, just return header
                return header

        if code_lines is None or not diagnostic.line:
            return header

        context_lines = []
        previous_line = -1
        for line, column in zip(lines, columns):
            line += 1  # Convert to 1-based index
            # Show context: 1 line above, current line, 1 line below
            start_line = max(1, line - 1)
            end_line = min(len(code_lines), line + 1)
            if previous_line != -1 and start_line > previous_line + 2:
                context_lines.append("   ...")

            for i in range(start_line, end_line + 1):
                line_content = (
                    code_lines[i - 1] if i <= len(code_lines) else ""
                )
                line_num = cyan(f"{i:4d} |")

                if i == line:
                    # Current line with error indicator
                    context_lines.append(f"{line_num} {line_content}")
                    # Add error indicator line
                    indicator = " " * 5 + " " * (column - 2) + red("^" * 1)
                    context_lines.append(f"     {cyan('|')}{indicator}")
                else:
                    context_lines.append(f"{line_num} {line_content}")
            previous_line = end_line

        if diagnostic.fix:
            context_lines.append(light_blue("hint: ") + bold(diagnostic.fix))
        return f"{header}\n" + "\n".join(context_lines) + "\n"
