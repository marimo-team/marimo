# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from marimo._ast.parse import NotebookSerialization
from marimo._cli.print import bold, cyan, red, yellow
from marimo._types.ids import CellId_t


class Severity(Enum):
    """Severity levels for lint errors."""

    FORMATTING = "formatting" # prefix: MF0000
    RUNTIME = "runtime"       # prefix: MR0000
    BREAKING = "breaking"     # prefix: MB0000


def line_num(line: int) -> str:
    """Format line number for display."""
    return f"{line:4d}"


@dataclass
class LintError:
    """Represents a lint error found in a notebook."""

    code: str
    name: str
    message: str
    severity: Severity
    cell_id: None | list[CellId_t]
    line: int | list[int]
    column: int | list[int]
    fixable: bool
    fix: Optional[str] = None

    def format(
        self, filename: str, code_lines: list[str] | None = None
    ) -> str:
        """Format the error for display with code context."""
        severity_color = {
            Severity.FORMATTING: yellow,
            Severity.RUNTIME: red,
            Severity.BREAKING: red,
        }.get(self.severity, bold)
        severity_str = {
            Severity.FORMATTING: "warning",
            Severity.RUNTIME: "error",
            Severity.BREAKING: "critical",
        }.get(self.severity, "info")

        lines = self.line if isinstance(self.line, list) else [self.line]
        columns = (
            self.column if isinstance(self.column, list) else [self.column]
        )

        location = (
            f"{filename}:{lines[0]}:{columns[0]}"
            if max(lines + [0]) > 0
            else filename
        )
        header = f"{bold(severity_color(severity_str + '[' + self.name + ']'))}: {bold(self.message)}"
        header += "\n" + cyan(" --> ") + cyan(location)

        if code_lines is None or not self.line:
            return header

        context_lines = []
        previous_line = -1
        for line, column in sorted(zip(lines, columns)):
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

                if i == line + 1:
                    # Current line with error indicator
                    context_lines.append(f"{line_num} {line_content}")
                    # Add error indicator line
                    indicator = " " * 5 + " " * (column - 2) + red("^" * 1)
                    context_lines.append(f"     {cyan('|')}{indicator}")
                else:
                    context_lines.append(f"{line_num} {line_content}")
            previous_line = end_line

        if self.fix:
            context_lines.append(
                cyan("info: ") + bold(self.fix)
            )
        return f"{header}\n" + "\n".join(context_lines)


class LintRule(ABC):
    """Base class for lint rules."""

    def __init__(
        self,
        code: str,
        name: str,
        description: str,
        severity: Severity,
        fixable: bool,
    ):
        self.code = code
        self.name = name
        self.description = description
        self.severity = severity
        self.fixable = fixable

    @abstractmethod
    def check(self, notebook: NotebookSerialization) -> list[LintError]:
        """Check notebook for violations of this rule."""
        pass
