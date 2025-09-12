# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import glob
from dataclasses import dataclass, field
from typing import AsyncIterator

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
    contents: str | None = None  # Store original file contents


class MarimoLinter:
    """High-level interface for linting and fixing marimo files.
    
    Consolidates checker functionality with file processing and async operations.
    """
    
    def __init__(self, file_patterns: tuple[str, ...], early_stopping: EarlyStoppingConfig | None = None):
        self.checker = LintChecker.create_default(early_stopping)
        self.files: list[FileStatus] = []
        self.errored: bool = False
        self.file_patterns = file_patterns
    
    def run(self) -> None:
        """Add files matching patterns to be processed."""
        # Expand glob patterns to find files
        file_patterns = self.file_patterns
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
                self.files.append(file_status)
                continue

            # Parse file as notebook (this reads the file internally)
            try:
                load_result = get_notebook_status(file_path)
            except SyntaxError as e:
                # Handle syntax errors in notebooks
                file_status.failed = True
                file_status.message = f"Failed to parse: {file_path}"
                file_status.details = [f"SyntaxError: {str(e)}"]
                self.files.append(file_status)
                continue

            file_status.notebook = load_result.notebook
            file_status.contents = load_result.contents
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
                    file_status.diagnostics = self.checker.check_notebook_sync(load_result.notebook)
                except Exception as e:
                    # Handle other parsing errors
                    file_status.failed = True
                    file_status.message = f"Failed to process {file_path}"
                    file_status.details = [str(e)]
                    self.errored = True
            else:
                # Status is valid but no notebook - shouldn't happen but handle gracefully
                file_status.skipped = True
                file_status.message = f"Skipped: {file_path} (no notebook content)"

            self.files.append(file_status)
    
    async def check_async(self, file_patterns: tuple[str, ...]) -> AsyncIterator[FileStatus]:
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
                file_status.message = f"Skipped: {file_path} (not a notebook file)"
                return file_status

            # Parse file as notebook
            try:
                load_result = get_notebook_status(file_path)
            except SyntaxError as e:
                # Handle syntax errors in notebooks
                file_status.failed = True
                file_status.message = f"Failed to parse: {file_path}"
                file_status.details = [f"SyntaxError: {str(e)}"]
                return file_status

            file_status.notebook = load_result.notebook
            file_status.contents = load_result.contents
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
                    file_status.diagnostics = await self.checker.check_notebook(load_result.notebook)
                except Exception as e:
                    # Handle other parsing errors
                    file_status.failed = True
                    file_status.message = f"Failed to process {file_path}"
                    file_status.details = [str(e)]
                    self.errored = True
            else:
                # Status is valid but no notebook - shouldn't happen but handle gracefully
                file_status.skipped = True
                file_status.message = f"Skipped: {file_path} (no notebook content)"
            
            return file_status
        
        # Create tasks for all files
        tasks = [asyncio.create_task(process_file(file_path)) for file_path in files_to_check]
        
        # Yield results as they complete
        for task in asyncio.as_completed(tasks):
            file_status = await task
            self.files.append(file_status)
            yield file_status
    
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
        fixable_files = [fs for fs in self.files if not (fs.skipped or fs.failed or fs.notebook is None)]
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
                lambda: Path(file_status.file).write_text(generated_contents, encoding="utf-8")
            )
            return True
        
        return False


def run_check(file_patterns: tuple[str, ...]) -> MarimoLinter:
    """Run linting checks on files matching patterns (CLI entry point).

    High-level interface that handles file discovery, parsing, and aggregation.
    Used by the `marimo check` command.

    Args:
        file_patterns: Glob patterns for file discovery

    Returns:
        MarimoLinter with per-file status and diagnostics
    """
    linter = MarimoLinter(file_patterns)
    linter.run()
    return linter


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
    "MarimoLinter",
    "FileStatus",
]
