# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import glob
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._ast.load import get_notebook_status
from marimo._ast.parse import MarimoFileError
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.rule_engine import EarlyStoppingConfig, RuleEngine
from marimo._lint.rules.base import LintRule
from marimo._lint.rules.breaking import UnparsableRule
from marimo._lint.rules.formatting import GeneralFormattingRule
from marimo._lint.rules.parsing import ParseDiagnosticsRule
from marimo._lint.rules.runtime import (
    CycleDependenciesRule,
    MultipleDefinitionsRule,
    SetupCellDependenciesRule,
)
from marimo._schemas.serialization import NotebookSerialization

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def lint_notebook(notebook: NotebookSerialization) -> list[Diagnostic]:
    """Lint a notebook and return all diagnostics found.

    Args:
        notebook: The notebook serialization to lint (should include filename)

    Returns:
        List of diagnostics found in the notebook
    """
    # Create a temporary rule engine just for this notebook
    rule_engine = RuleEngine.create_default()
    return rule_engine.check_notebook_sync(notebook)


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
    contents: str | None = None  # Store original file contents


class Linter:
    """High-level interface for linting and fixing marimo files.

    Orchestrates file-level processing and delegates notebook linting to RuleEngine.
    """

    def __init__(
        self,
        early_stopping: EarlyStoppingConfig | None = None,
    ):
        # Use composition - delegate notebook checking to RuleEngine
        self.rule_engine = RuleEngine.create_default(early_stopping)

        # File processing state
        self.files: list[FileStatus] = []
        self.errored: bool = False

    async def _run_stream(
        self, file_patterns: tuple[str, ...]
    ) -> AsyncIterator[FileStatus]:
        """Asynchronously check files and yield results as they complete."""
        # Expand glob patterns to find files
        files_to_check = []
        for pattern in file_patterns:
            files_to_check.extend(glob.glob(pattern, recursive=True))

        # Remove duplicates and sort
        files_to_check = sorted(set(files_to_check))

        # Create tasks for all files
        async def process_file(file_path: str) -> FileStatus:
            file_status = FileStatus(file=file_path)

            # Check if file is a supported notebook format
            if not file_path.endswith((".py", ".md", ".qmd")):
                file_status.skipped = True
                file_status.message = (
                    f"Skipped: {file_path} (not a notebook file)"
                )
                return file_status

            # Parse file as notebook and capture stdout/stderr for formatting diagnostics
            import contextlib
            import io

            captured_stdout = io.StringIO()
            captured_stderr = io.StringIO()

            try:
                with (
                    contextlib.redirect_stdout(captured_stdout),
                    contextlib.redirect_stderr(captured_stderr),
                ):
                    load_result = get_notebook_status(file_path)
            except SyntaxError as e:
                # Handle syntax errors in notebooks
                file_status.failed = True
                file_status.message = f"Failed to parse: {file_path}"
                file_status.details = [f"SyntaxError: {str(e)}"]
                return file_status
            except MarimoFileError as e:
                # Handle syntax errors in notebooks
                file_status.failed = True
                file_status.message = (
                    f"Not recognizable as a marimo notebook: {file_path}"
                )
                file_status.details = [f"MarimoFileError: {str(e)}"]
                return file_status

            file_status.notebook = load_result.notebook
            file_status.contents = load_result.contents

            # Capture stdout/stderr for processing by ParseDiagnosticsRule
            stdout_content = captured_stdout.getvalue().strip()
            stderr_content = captured_stderr.getvalue().strip()
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
                    # Create a temporary rule engine that includes parsing diagnostics
                    temp_rules = list(self.rule_engine.rules)

                    # Add parsing rule if there's captured output
                    if stdout_content or stderr_content:
                        parse_rule = ParseDiagnosticsRule(
                            stdout_content, stderr_content
                        )
                        temp_rules.append(parse_rule)

                    # Create temporary engine with parsing rule
                    from marimo._lint.rule_engine import RuleEngine

                    temp_engine = RuleEngine(
                        temp_rules, self.rule_engine.early_stopping
                    )

                    # Check notebook with all rules including parsing
                    file_status.diagnostics = await temp_engine.check_notebook(
                        load_result.notebook
                    )
                except Exception as e:
                    # Handle other parsing errors
                    file_status.failed = True
                    file_status.message = f"Failed to process {file_path}"
                    file_status.details = [str(e)]
                    self.errored = True
            else:
                # Status is valid but no notebook - shouldn't happen but handle gracefully
                file_status.skipped = True
                file_status.message = (
                    f"Skipped: {file_path} (no notebook content)"
                )

            # Ensure diagnostics list is initialized for cases where no processing happened
            if not hasattr(file_status, "diagnostics"):
                file_status.diagnostics = []

            return file_status

        # Create tasks for all files
        tasks = [
            asyncio.create_task(process_file(file_path))
            for file_path in files_to_check
        ]

        # Yield results as they complete
        for task in asyncio.as_completed(tasks):
            file_status = await task
            self.files.append(file_status)
            yield file_status

    async def _run_async(
        self, file_patterns: tuple[str, ...]
    ) -> list[FileStatus]:
        """Internal async implementation of run."""
        return [
            file_status
            async for file_status in self._run_stream(file_patterns)
        ]

    def run(self, file_patterns: tuple[str, ...]) -> list[FileStatus]:
        """Run linting checks on files matching patterns.

        Args:
            file_patterns: Glob patterns for file discovery

        Returns:
            List of FileStatus objects with per-file results
        """
        # Run the async operation and collect results
        files = asyncio.run(self._run_async(file_patterns))
        return list(files)

    def fix_all(self) -> int:
        """Fix all files that can be fixed concurrently.

        Returns:
            Number of files that were actually fixed
        """
        # Run the async fix operation
        return asyncio.run(self._fix_all_async())

    async def _fix_all_async(self) -> int:
        """Internal async implementation of fix_all."""
        # Create tasks for all eligible files
        fixable_files = [
            fs
            for fs in self.files
            if not (fs.skipped or fs.failed or fs.notebook is None)
        ]
        tasks = [asyncio.create_task(self.fix(fs)) for fs in fixable_files]

        # Wait for all fixes to complete
        results = await asyncio.gather(*tasks)

        return sum(results)

    @staticmethod
    async def fix(file_status: FileStatus) -> bool:
        """Fix a single file and write to disk.

        Returns:
            True if file was modified and written, False otherwise
        """
        if file_status.notebook is None or file_status.contents is None:
            return False

        is_markdown = file_status.file.endswith((".md", ".qmd"))

        if is_markdown:
            from marimo._server.export.exporter import Exporter

            exporter = Exporter()
            generated_contents, _ = exporter.export_as_md(
                file_status.notebook, file_status.file
            )
        else:
            from marimo._ast import codegen
            from marimo._ast.app_config import _AppConfig as AppConfig
            from marimo._ast.cell import CellConfig

            generated_contents = codegen.generate_filecontents(
                codes=[cell.code for cell in file_status.notebook.cells],
                names=[cell.name for cell in file_status.notebook.cells],
                cell_configs=[
                    CellConfig.from_dict(cell.options, warn=False)
                    for cell in file_status.notebook.cells
                ],
                config=AppConfig.from_untrusted_dict(
                    file_status.notebook.app.options, silent=True
                ),
                header_comments=file_status.notebook.header.value
                if file_status.notebook.header
                else None,
            )

        # Only write if content changed
        if file_status.contents != generated_contents:
            # Run IO in executor to keep it async
            from pathlib import Path

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: Path(file_status.file).write_text(
                    generated_contents, encoding="utf-8"
                ),
            )
            return True

        return False


def run_check(file_patterns: tuple[str, ...]) -> Linter:
    """Run linting checks on files matching patterns (CLI entry point).

    High-level interface that handles file discovery, parsing, and aggregation.
    Used by the `marimo check` command.

    Args:
        file_patterns: Glob patterns for file discovery

    Returns:
        Linter with per-file status and diagnostics
    """
    linter = Linter()
    linter.run(file_patterns)
    return linter


__all__ = [
    "Diagnostic",
    "LintRule",
    "Severity",
    "EarlyStoppingConfig",
    "RuleEngine",
    "GeneralFormattingRule",
    "MultipleDefinitionsRule",
    "CycleDependenciesRule",
    "SetupCellDependenciesRule",
    "UnparsableRule",
    "lint_notebook",
    "run_check",
    "Linter",
    "FileStatus",
]
