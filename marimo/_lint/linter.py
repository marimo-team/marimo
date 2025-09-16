# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._ast.load import get_notebook_status
from marimo._ast.parse import MarimoFileError
from marimo._cli.print import red
from marimo._convert.converters import MarimoConvert
from marimo._lint.diagnostic import Diagnostic
from marimo._lint.rule_engine import EarlyStoppingConfig, RuleEngine
from marimo._schemas.serialization import NotebookSerialization

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable


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
        pipe: Callable[[str], None] | None = None,
        fix_files: bool = False,
    ):
        self.rule_engine = RuleEngine.create_default(early_stopping)
        self.pipe = pipe
        self.fix_files = fix_files
        self.files: list[FileStatus] = []

        # File processing state
        self.errored: bool = False

        # Counters for summary
        self.fixed_count: int = 0
        self.issues_count: int = 0

    async def _run_stream(
        self, files_to_check: list[Path]
    ) -> AsyncIterator[FileStatus]:
        """Asynchronously check files and yield results as they complete."""

        # Create tasks for all files
        async def process_file(file: Path) -> FileStatus:
            file_path = str(file)
            file_status = FileStatus(file=file_path)

            # Check if file is a supported notebook format
            if not file_path.endswith((".py", ".md", ".qmd")):
                file_status.skipped = True
                file_status.message = (
                    f"Skipped: {file_path} (not a notebook file)"
                )
                return file_status

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
                self.errored = True
                file_status.failed = True
                file_status.message = f"Failed to parse: {file_path}"
                file_status.details = [f"SyntaxError: {str(e)}"]
                return file_status
            except MarimoFileError as e:
                # Handle syntax errors in notebooks
                self.errored = True
                file_status.failed = True
                file_status.message = (
                    f"Not recognizable as a marimo notebook: {file_path}"
                )
                file_status.details = [f"MarimoFileError: {str(e)}"]
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
                    # Check notebook with all rules including parsing
                    file_status.diagnostics = (
                        await self.rule_engine.check_notebook(
                            load_result.notebook,
                            # Add parsing rule if there's captured output
                            stdout=captured_stdout.getvalue().strip(),
                            stderr=captured_stderr.getvalue().strip(),
                        )
                    )
                except Exception as e:
                    # Handle other parsing errors
                    self.errored = True
                    file_status.failed = True
                    file_status.message = f"Failed to process {file_path}"
                    file_status.details = [str(e)]
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
            yield file_status

    def _pipe_file_status(self, file_status: FileStatus) -> None:
        """Send file status through pipe for real-time output."""
        for diagnostic in file_status.diagnostics:
            if not (self.fix_files and diagnostic.fixable):
                self.issues_count += 1

        if not self.pipe:
            return

        if file_status.skipped:
            # Don't output skipped files unless they failed
            return
        elif file_status.failed:
            self.pipe(red(file_status.message))
            for detail in file_status.details:
                self.pipe(red(f"{detail}"))
        else:
            # Show diagnostics immediately as they're found
            for diagnostic in file_status.diagnostics:
                self.pipe(diagnostic.format())
                self.pipe("")  # Empty line for spacing

    @staticmethod
    def _generate_file_contents(file_status: FileStatus) -> str:
        """Generate file contents from notebook serialization."""
        if file_status.notebook is None:
            raise ValueError(
                "Cannot generate contents for file without notebook"
            )

        converter = MarimoConvert.from_ir(file_status.notebook)

        if file_status.file.endswith((".md", ".qmd")):
            return converter.to_markdown(file_status.file)
        else:
            return converter.to_py()

    def run_streaming(self, files_to_check: list[Path]) -> None:
        """Run linting checks with real-time streaming output."""
        asyncio.run(self._run_streaming_async(files_to_check))

    async def _run_streaming_async(self, files_to_check: list[Path]) -> None:
        """Internal async implementation of run_streaming."""
        # Process files as they complete
        fixed_count = 0
        async for file_status in self._run_stream(files_to_check):
            self.files.append(file_status)

            # Stream output via pipe if available
            if self.pipe:
                self._pipe_file_status(file_status)

            # Add to fix queue and potentially fix if requested
            if self.fix_files and not (
                file_status.skipped
                or file_status.failed
                or file_status.notebook is None
            ):
                if await self.fix(file_status):
                    fixed_count += 1
                    if self.pipe:
                        self.pipe(f"Updated: {file_status.file}")
        self.fixed_count = fixed_count

    @staticmethod
    async def fix(file_status: FileStatus) -> bool:
        """Fix a single file and write to disk.

        Returns:
            True if file was modified and written, False otherwise
        """
        if file_status.notebook is None or file_status.contents is None:
            return False

        generated_contents = Linter._generate_file_contents(file_status)

        # Only write if content changed
        if file_status.contents != generated_contents:
            await asyncio.to_thread(
                Path(file_status.file).write_text,
                generated_contents,
                encoding="utf-8",
            )
            return True

        return False
