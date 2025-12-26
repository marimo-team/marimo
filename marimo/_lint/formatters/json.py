# Copyright 2026 Marimo. All rights reserved.
"""JSON formatter and types for lint output."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal, TypedDict, Union

from marimo._lint.formatters.base import DiagnosticFormatter
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._lint.diagnostic import Diagnostic


class DiagnosticJSON(TypedDict, total=False):
    """Typed structure for diagnostic JSON output."""

    # Required fields
    type: Literal["diagnostic"]
    message: str
    filename: str
    line: int
    column: int

    # Optional fields
    lines: list[int]
    columns: list[int]
    severity: Literal["formatting", "runtime", "breaking"]
    name: str
    code: str
    fixable: Union[bool, Literal["unsafe"]]
    fix: str
    cell_id: list[CellId_t]


class FileErrorJSON(TypedDict):
    """Typed structure for file-level errors."""

    type: Literal["error"]
    filename: str
    error: str


class SummaryJSON(TypedDict):
    """Typed structure for summary JSON output."""

    total_files: int
    files_with_issues: int
    total_issues: int
    fixed_issues: int
    errored: bool


# Union type for all issue types
IssueJSON = Union[DiagnosticJSON, FileErrorJSON]


class LintResultJSON(TypedDict):
    """Typed structure for complete lint result JSON output."""

    issues: list[IssueJSON]
    summary: SummaryJSON


class JSONFormatter(DiagnosticFormatter):
    """JSON formatter that outputs diagnostics as structured JSON."""

    def format(
        self,
        diagnostic: Diagnostic,
        filename: str,
        code_lines: list[str] | None = None,  # noqa: ARG002
    ) -> str:
        """Format the diagnostic as JSON."""
        return json.dumps(
            self.to_json_dict(diagnostic, filename), ensure_ascii=False
        )

    def to_json_dict(
        self, diagnostic: Diagnostic, filename: str
    ) -> DiagnosticJSON:
        """Convert diagnostic to typed JSON dictionary."""
        lines, columns = diagnostic.sorted_lines

        # Build complete dict with all fields
        result = {
            "type": "diagnostic",
            "message": diagnostic.message,
            "filename": filename,
            "line": lines[0] if lines else 0,
            "column": columns[0] if columns else 0,
            "lines": list(lines) if len(lines) > 1 else None,
            "columns": list(columns) if len(columns) > 1 else None,
            "severity": diagnostic.severity.value
            if diagnostic.severity
            else None,
            "name": diagnostic.name,
            "code": diagnostic.code,
            "fixable": diagnostic.fixable,
            "fix": diagnostic.fix,
            "cell_id": diagnostic.cell_id,
        }

        # Filter out None values and return as typed dict
        filtered = {k: v for k, v in result.items() if v is not None}
        return DiagnosticJSON(filtered)  # type: ignore
