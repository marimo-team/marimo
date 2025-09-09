# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from marimo._types.ids import CellId_t


class Severity(Enum):
    """Severity levels for diagnostic errors."""

    FORMATTING = "formatting"  # prefix: MF0000
    RUNTIME = "runtime"       # prefix: MR0000
    BREAKING = "breaking"     # prefix: MB0000


def line_num(line: int) -> str:
    """Format line number for display."""
    return f"{line:4d}"


@dataclass
class Diagnostic:
    """Represents a diagnostic found in a notebook."""

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
        self,
        filename: str,
        code_lines: list[str] | None = None,
        formatter: str = "full"
    ) -> str:
        """Format the diagnostic for display.

        Args:
            filename: The filename where the diagnostic occurred
            code_lines: Optional source code lines for context
            formatter: The formatter to use ("full" is the only supported option)

        Returns:
            Formatted diagnostic string
        """
        from marimo._lint.formatter import FullFormatter

        if formatter == "full":
            fmt = FullFormatter()
            return fmt.format(self, filename, code_lines)
        else:
            raise ValueError(f"Unsupported formatter: {formatter}")
