# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import glob
from dataclasses import dataclass, field

from marimo._ast.load import get_notebook_status
from marimo._lint.checker import EarlyStoppingConfig, LintChecker
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking import UnparsableRule
from marimo._lint.rules.formatting import GeneralFormattingRule
from marimo._lint.rules.runtime import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
)
from marimo._schemas.serialization import NotebookSerialization


def lint_notebook(notebook: NotebookSerialization) -> list[Diagnostic]:
    """Lint a notebook and return all diagnostics found.

    Args:
        notebook: The notebook serialization to lint (should include filename)

    Returns:
        List of diagnostics found in the notebook
    """
    checker = LintChecker.create_default()
    return checker.check_notebook_sync(notebook)


@dataclass
class FileStatus:
    """Processing status and results for a single file."""

    file: str  # File path
    diagnostics: list[Diagnostic] = field(
        default_factory=list
    )  # Found diagnostics
    skipped: bool = False  # File skipped (not a notebook)
    failed: bool = False  # Parsing/processing failed
    message: str = ""  # Status message
    details: list[str] = field(default_factory=list)  # Error details
    notebook: NotebookSerialization | None = None

    def fix(self) -> None | str:
        """Generate fixed content applying specified fix level.

        Returns:
            Fixed file content with diagnostics resolved
        """
        # TODO: level: Literal["all", ...] = "all"
        # for filtering "fixes" based on severity

        if self.notebook is None:
            return

        is_markdown = self.file.endswith((".md", ".qmd"))

        if is_markdown:
            from marimo._server.export.exporter import Exporter

            exporter = Exporter()
            generated_contents, _ = exporter.export_as_md(
                self.notebook, self.file
            )
        else:
            from marimo._ast import codegen
            from marimo._ast.app_config import _AppConfig as AppConfig
            from marimo._ast.cell import CellConfig

            generated_contents = codegen.generate_filecontents(
                codes=[cell.code for cell in self.notebook.cells],
                names=[cell.name for cell in self.notebook.cells],
                cell_configs=[
                    CellConfig.from_dict(cell.options, warn=False)
                    for cell in self.notebook.cells
                ],
                config=AppConfig.from_untrusted_dict(
                    self.notebook.app.options, silent=True
                ),
                header_comments=self.notebook.header.value
                if self.notebook.header
                else None,
            )

        return generated_contents


@dataclass
class CheckResult:
    """Aggregated results from checking multiple files."""

    # Consolisdate with LintChecker

    files: list[FileStatus] = field(default_factory=list)  # Per-file results
    errored: bool = False  # Any file failed to process

    # fix (taking a filestatus, and noteboo) should also live on LintChecker


def run_check(file_patterns: tuple[str, ...]) -> CheckResult:
    """Run linting checks on files matching patterns (CLI entry point).

    High-level interface that handles file discovery, parsing, and aggregation.
    Used by the `marimo check` command.

    Args:
        file_patterns: Glob patterns for file discovery

    Returns:
        CheckResult with per-file status and diagnostics
    """
    result = CheckResult()

    # Expand glob patterns to find files
    files_to_check = []
    for pattern in file_patterns:
        files_to_check.extend(glob.glob(pattern, recursive=True))

    # Remove duplicates and sort
    files_to_check = sorted(set(files_to_check))

    for file_path in files_to_check:
        file_status = FileStatus(file=file_path)
        # Check if file is a supported notebook format
        if not file_path.endswith((".py", ".md", ".qmd")):
            file_status.skipped = True
            file_status.message = f"Skipped: {file_path} (not a notebook file)"
            result.files.append(file_status)
            continue

        # Parse file as notebook
        try:
            load_result = get_notebook_status(file_path)
        except SyntaxError as e:
            # Handle syntax errors in notebooks
            file_status.failed = True
            file_status.message = f"Failed to parse: {file_path}"
            file_status.details = [f"SyntaxError: {str(e)}"]
            result.files.append(file_status)
            continue

        file_status.notebook = load_result.notebook
        if load_result.status == "empty":
            file_status.skipped = True
            file_status.message = f"Skipped: {file_path} (empty file)"
        elif load_result.status == "invalid":
            file_status.failed = True
            file_status.message = (
                f"Failed to parse: {file_path} (not a valid notebook)"
            )
        elif load_result.notebook is not None:
            try:
                file_status.diagnostics = lint_notebook(load_result.notebook)
            except Exception as e:
                # Handle other parsing errors
                file_status.failed = True
                file_status.message = f"Failed to process {file_path}"
                file_status.details = [str(e)]
                result.errored = True
        else:
            # Status is valid but no notebook - shouldn't happen but handle gracefully
            file_status.skipped = True
            file_status.message = f"Skipped: {file_path} (no notebook content)"

        result.files.append(file_status)

    return result


__all__ = [
    "Diagnostic",
    "LintRule",
    "Severity",
    "LintChecker",
    "EarlyStoppingConfig",
    "GeneralFormattingRule",
    "MultipleDefinitionsRule",
    "CycleDependenciesRule",
    "SetupCellDependenciesRule",
    "UnparsableRule",
    "lint_notebook",
    "run_check",
    "CheckResult",
    "FileStatus",
]
