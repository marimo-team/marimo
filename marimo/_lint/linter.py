# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Union

from marimo._ast.load import get_notebook_status
from marimo._ast.parse import MarimoFileError
from marimo._cli.print import red
from marimo._convert.converters import MarimoConvert
from marimo._lint.diagnostic import Diagnostic, Severity
from marimo._lint.formatters import LintResultJSON
from marimo._lint.rule_engine import EarlyStoppingConfig, RuleEngine
from marimo._loggers import capture_output
from marimo._schemas.serialization import NotebookSerialization
from marimo._utils import async_path

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from marimo._lint.rules.base import LintRule


def contents_differ_excluding_generated_with(
    original: str, generated: str
) -> bool:
    """Compare file contents while ignoring __generated_with differences.

    This prevents unnecessary file writes when only the __generated_with
    version metadata differs between the original and generated content.
    """
    # Regex to match the __generated_with line
    pattern = r"^__generated_with = .*$"

    # Remove __generated_with lines from both contents
    orig_cleaned = re.sub(pattern, "", original, flags=re.MULTILINE).strip()
    gen_cleaned = re.sub(pattern, "", generated, flags=re.MULTILINE).strip()

    return orig_cleaned != gen_cleaned


async def _to_async_iterator(
    files_to_check: Union[AsyncIterator[Path], Iterator[Path]],
) -> AsyncIterator[Path]:
    """Convert a regular iterator to an async iterator if needed."""
    if hasattr(files_to_check, "__aiter__"):
        # Already an async iterator
        async for file_path in files_to_check:
            yield file_path
    else:
        # Convert regular iterator to async
        for file_path in files_to_check:
            yield file_path


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
        unsafe_fixes: bool = False,
        rules: list[LintRule] | None = None,
        ignore_scripts: bool = False,
        formatter: str = "full",
    ):
        if rules is not None:
            self.rule_engine = RuleEngine(rules, early_stopping)
        else:
            self.rule_engine = RuleEngine.create_default(early_stopping)
        self.pipe = pipe
        self.fix_files = fix_files
        self.unsafe_fixes = unsafe_fixes
        self.ignore_scripts = ignore_scripts
        self.formatter = formatter
        self.files: list[FileStatus] = []

        # Create rule lookup for unsafe fixes
        self.rule_lookup = {rule.code: rule for rule in self.rule_engine.rules}

        # File processing state
        self.errored: bool = False

        # Counters for summary
        self.fixed_count: int = 0
        self.issues_count: int = 0

    async def _process_single_file(self, file: Path) -> FileStatus:
        """Process a single file and return its status."""
        file_path = str(file)
        file_status = FileStatus(file=file_path)
        # Check if file exists first
        if not await async_path.exists(file):
            self.errored = True
            file_status.failed = True
            file_status.message = f"File not found: {file_path}"
            file_status.details = [
                f"FileNotFoundError: No such file or directory: '{file_path}'"
            ]
            return file_status

        # Check if file is a supported notebook format
        if not file_path.endswith((".py", ".md", ".qmd")):
            file_status.skipped = True
            file_status.message = f"Skipped: {file_path} (not a notebook file)"
            return file_status

        try:
            with capture_output() as (stdout, stderr, logs):
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
            if self.ignore_scripts:
                # Skip this file silently when ignore_scripts is enabled
                file_status.skipped = True
                file_status.message = (
                    f"Skipped: {file_path} (not a marimo notebook)"
                )
                return file_status
            else:
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
            if self.ignore_scripts:
                # Skip this file silently when ignore_scripts is enabled
                file_status.skipped = True
                file_status.message = (
                    f"Skipped: {file_path} (not a marimo notebook)"
                )
                return file_status
            else:
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
                        load_result.contents or "",
                        # Add parsing rule if there's captured output
                        stdout=stdout.getvalue().strip(),
                        stderr=stderr.getvalue().strip(),
                        logs=logs,
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
            file_status.message = f"Skipped: {file_path} (no notebook content)"

        # Ensure diagnostics list is initialized for cases where no processing happened
        if not hasattr(file_status, "diagnostics"):
            file_status.diagnostics = []

        return file_status

    async def _run_stream(
        self, files_to_check: list[Path]
    ) -> AsyncIterator[FileStatus]:
        """Asynchronously check files and yield results as they complete."""

        # Create tasks for all files
        tasks = [
            asyncio.create_task(self._process_single_file(file_path))
            for file_path in files_to_check
        ]

        # Yield results as they complete
        for task in asyncio.as_completed(tasks):
            file_status = await task
            yield file_status

    def _pipe_file_status(self, file_status: FileStatus) -> None:
        """Send file status through pipe for real-time output."""
        for diagnostic in file_status.diagnostics:
            will_fix = self.fix_files and (
                diagnostic.fixable is True
                or (diagnostic.fixable == "unsafe" and self.unsafe_fixes)
            )
            if not will_fix:
                self.issues_count += 1
            if diagnostic.severity == Severity.BREAKING:
                self.errored = True

        if file_status.failed:
            self.errored = True

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
                self.pipe(diagnostic.format(formatter=self.formatter))

    @staticmethod
    def _generate_file_contents_from_notebook(
        notebook: NotebookSerialization, filename: str
    ) -> str:
        """Generate file contents from notebook serialization."""
        converter = MarimoConvert.from_ir(notebook)

        with capture_output():
            if filename.endswith((".md", ".qmd")):
                return converter.to_markdown()
            else:
                return converter.to_py()

    @staticmethod
    def _generate_file_contents(file_status: FileStatus) -> str:
        """Generate file contents from notebook serialization."""
        if file_status.notebook is None:
            raise ValueError(
                "Cannot generate contents for file without notebook"
            )

        return Linter._generate_file_contents_from_notebook(
            file_status.notebook, file_status.file
        )

    def run_streaming(
        self, files_to_check: Union[AsyncIterator[Path], Iterator[Path]]
    ) -> None:
        """Run linting checks with real-time streaming output."""
        asyncio.run(self._run_streaming_async(files_to_check))

    async def _run_streaming_async(
        self, files_to_check: Union[AsyncIterator[Path], Iterator[Path]]
    ) -> None:
        """Internal async implementation of run_streaming."""
        # Process files as they complete
        fixed_count = 0

        # Convert to async iterator and process
        async for file_path in _to_async_iterator(files_to_check):
            file_status = await self._process_single_file(file_path)
            self.files.append(file_status)

            # Stream output via pipe if available
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

    async def fix(self, file_status: FileStatus) -> bool:
        """Fix a single file and write to disk.

        Returns:
            True if file was modified and written, False otherwise
        """
        if file_status.notebook is None or file_status.contents is None:
            return False

        # Apply unsafe fixes if enabled
        modified_notebook = file_status.notebook
        if self.unsafe_fixes:
            # Collect diagnostics by rule code
            from collections import defaultdict

            from marimo._lint.rules.base import UnsafeFixRule

            diagnostics_by_rule = defaultdict(list)
            for diagnostic in file_status.diagnostics:
                if (
                    diagnostic.fixable == "unsafe"
                    and diagnostic.code in self.rule_lookup
                ):
                    diagnostics_by_rule[diagnostic.code].append(diagnostic)

            # Apply unsafe fixes once per rule
            for rule_code, diagnostics in diagnostics_by_rule.items():
                rule = self.rule_lookup[rule_code]
                if isinstance(rule, UnsafeFixRule):
                    # Apply fix once per rule with all its diagnostics
                    modified_notebook = rule.apply_unsafe_fix(
                        modified_notebook, diagnostics
                    )

        # Generate file contents from (possibly modified) notebook
        generated_contents = Linter._generate_file_contents_from_notebook(
            modified_notebook, file_status.file
        )

        # Only write if content changed (excluding __generated_with differences)
        if contents_differ_excluding_generated_with(
            file_status.contents, generated_contents
        ):
            await asyncio.to_thread(
                Path(file_status.file).write_text,
                generated_contents,
                encoding="utf-8",
            )
            return True

        return False

    def get_json_result(self) -> LintResultJSON:
        """Get complete JSON result with diagnostics and summary."""
        from marimo._lint.formatters import (
            FileErrorJSON,
            IssueJSON,
            JSONFormatter,
        )

        json_formatter = JSONFormatter()
        issues: list[IssueJSON] = []

        for file_status in self.files:
            if file_status.failed:
                # Add file-level errors
                error: FileErrorJSON = {
                    "type": "error",
                    "filename": file_status.file,
                    "error": file_status.message,
                }
                issues.append(error)
            elif not file_status.skipped:
                # Add diagnostics from successfully processed files
                for diagnostic in file_status.diagnostics:
                    diagnostic_dict = json_formatter.to_json_dict(
                        diagnostic, file_status.file
                    )
                    issues.append(diagnostic_dict)

        return LintResultJSON(
            issues=issues,
            summary={
                "total_files": len(self.files),
                "files_with_issues": len(
                    [
                        f
                        for f in self.files
                        if (f.diagnostics and not f.skipped and not f.failed)
                        or f.failed
                    ]
                ),
                "total_issues": self.issues_count,
                "fixed_issues": self.fixed_count,
                "errored": self.errored,
            },
        )
