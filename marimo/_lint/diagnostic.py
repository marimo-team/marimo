# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional, cast

from marimo._types.ids import CellId_t


class Severity(Enum):
    """Severity levels for diagnostic errors."""

    FORMATTING = "formatting"  # prefix: MF0000
    RUNTIME = "runtime"  # prefix: MR0000
    BREAKING = "breaking"  # prefix: MB0000


def line_num(line: int) -> str:
    """Format line number for display."""
    return f"{line:4d}"


@dataclass
class Diagnostic:
    """Represents a diagnostic found in a notebook."""

    message: str
    line: int | list[int]
    column: int | list[int]
    cell_id: None | list[CellId_t] = None
    code: Optional[str] = None
    name: Optional[str] = None
    severity: Optional[Severity] = None
    fixable: bool | Literal["unsafe"] | None = None
    fix: Optional[str] = None
    filename: Optional[str] = None

    def format(
        self,
        code_lines: list[str] | None = None,
        formatter: str = "full",
    ) -> str:
        """Format the diagnostic for display.

        Args:
            code_lines: Optional source code lines for context
            formatter: The formatter to use ("full" or "json")

        Returns:
            Formatted diagnostic string
        """
        from marimo._lint.formatters import (
            DiagnosticFormatter,
            FullFormatter,
            JSONFormatter,
        )

        actual_filename = self.filename or "unknown"

        if formatter == "full":
            fmt: DiagnosticFormatter = FullFormatter()
        elif formatter == "json":
            fmt = JSONFormatter()
        else:
            raise ValueError(f"Unsupported formatter: {formatter}")

        return fmt.format(self, actual_filename, code_lines)

    @property
    def sorted_lines(self) -> tuple[tuple[int], tuple[int]]:
        """Get sorted line numbers as a list."""
        lines: list[int] = (
            self.line if isinstance(self.line, list) else [self.line]
        )
        columns: list[int] = (
            self.column if isinstance(self.column, list) else [self.column]
        )
        # mypy seems unable to infer the type
        return cast(
            tuple[tuple[int], tuple[int]],
            tuple(zip(*sorted(zip(lines, columns)))),
        )
