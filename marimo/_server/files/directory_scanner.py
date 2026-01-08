# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from marimo import _loggers
from marimo._server.files.os_file_system import natural_sort_file
from marimo._server.models.files import FileInfo
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath

LOGGER = _loggers.marimo_logger()


def is_marimo_app(full_path: str) -> bool:
    """
    Detect whether a file is a marimo app.

    Rules:
    - Markdown (`.md`/`.qmd`) files are marimo apps if the first 512 bytes
      contain `marimo-version:`.
    - Python (`.py`) files are marimo apps if the header (first 512 bytes)
      contains both `marimo.App` and `import marimo`.
    - If the header contains `# /// script`, read the full file and check for
      the same Python markers, to handle large script headers.
    - Any errors while reading result in `False`.
    """
    READ_LIMIT = 512

    def contains_marimo_app(content: bytes) -> bool:
        return b"marimo.App" in content and b"import marimo" in content

    try:
        path = MarimoPath(full_path)

        with open(full_path, "rb") as f:
            header = f.read(READ_LIMIT)

        if path.is_markdown():
            return b"marimo-version:" in header

        if path.is_python():
            if contains_marimo_app(header):
                return True

            if b"# /// script" in header:
                full_content = path.read_bytes()
                if contains_marimo_app(full_content):
                    return True

        return False
    except Exception as e:
        LOGGER.debug("Error reading file %s: %s", full_path, e)
        return False


class DirectoryScanner:
    """Scans directories for marimo files with filtering and limits.

    Features:
    - Recursive directory traversal (max depth)
    - File type filtering (.py, .md, .qmd)
    - Skip common directories (venv, node_modules, etc.)
    - File count limits and timeouts
    - Marimo app detection
    """

    MAX_DEPTH = 5
    MAX_FILES = 1000
    MAX_EXECUTION_TIME = 10  # seconds

    SKIP_DIRS = {
        # Python virtual environments
        "venv",
        ".venv",
        ".virtualenv",
        "__pypackages__",
        # Python cache and build
        "__pycache__",
        "build",
        "dist",
        "eggs",
        # Package management
        "node_modules",
        "site-packages",
        # Testing and tooling
        ".tox",
        ".nox",
        ".pytest_cache",
        ".mypy_cache",
        # Version control
        ".git",
    }

    def __init__(
        self,
        directory: str,
        include_markdown: bool = False,
        max_files: Optional[int] = None,
        max_depth: Optional[int] = None,
        max_execution_time: Optional[int] = None,
    ):
        """Initialize DirectoryScanner.

        Args:
            directory: The directory to scan
            include_markdown: Whether to include .md and .qmd files
            max_files: Maximum number of files to find
            max_depth: Maximum directory depth to recurse
            max_execution_time: Maximum time in seconds before timeout
        """
        self.directory = directory
        self.include_markdown = include_markdown
        self.max_files = max_files if max_files is not None else self.MAX_FILES
        self.max_depth = max_depth if max_depth is not None else self.MAX_DEPTH
        self.max_execution_time = (
            max_execution_time
            if max_execution_time is not None
            else self.MAX_EXECUTION_TIME
        )
        # Stores partial results in case of timeout
        self.partial_results: list[FileInfo] = []

    @property
    def allowed_extensions(self) -> tuple[str, ...]:
        """Get allowed file extensions based on settings."""
        if self.include_markdown:
            return (".py", ".md", ".qmd")
        return (".py",)

    def scan(self) -> list[FileInfo]:
        """Scan directory and return file tree.

        Returns:
            List of FileInfo with nested children

        Raises:
            HTTPException: On timeout with REQUEST_TIMEOUT status.
                On timeout, partial_results will contain files found so far.
        """
        start_time = time.time()
        file_count = [0]  # Use list for closure mutability
        self.partial_results = []  # Reset partial results

        def recurse(
            directory: str, depth: int = 0
        ) -> Optional[list[FileInfo]]:
            if depth > self.max_depth:
                return None

            # Check file limit
            if file_count[0] >= self.max_files:
                LOGGER.warning(
                    f"Reached maximum file limit ({self.max_files})"
                )
                return None

            if time.time() - start_time > self.max_execution_time:
                # Store accumulated results before raising timeout
                raise HTTPException(
                    status_code=HTTPStatus.REQUEST_TIMEOUT,
                    detail=f"Request timed out: Loading workspace files took too long. Showing first {file_count[0]} files.",  # noqa: E501
                )

            try:
                entries = os.scandir(directory)
            except OSError as e:
                LOGGER.debug("OSError scanning directory: %s", str(e))
                return None

            files: list[FileInfo] = []
            folders: list[FileInfo] = []

            for entry in entries:
                # Skip hidden files and directories
                if entry.name.startswith("."):
                    continue

                if entry.is_dir():
                    if entry.name in self.SKIP_DIRS or depth == self.max_depth:
                        continue
                    children = recurse(entry.path, depth + 1)
                    if children:
                        entry_path = Path(entry.path)
                        relative_path = str(
                            entry_path.relative_to(self.directory)
                        )
                        folders.append(
                            FileInfo(
                                id=relative_path,
                                path=relative_path,
                                name=entry.name,
                                is_directory=True,
                                is_marimo_file=False,
                                children=children,
                            )
                        )
                elif entry.name.endswith(self.allowed_extensions):
                    if is_marimo_app(entry.path):
                        file_count[0] += 1
                        entry_path = Path(entry.path)
                        relative_path = str(
                            entry_path.relative_to(self.directory)
                        )
                        file_info = FileInfo(
                            id=relative_path,
                            path=relative_path,
                            name=entry.name,
                            is_directory=False,
                            is_marimo_file=True,
                            last_modified=entry.stat().st_mtime,
                        )
                        files.append(file_info)
                        # Also add to partial results for timeout recovery
                        self.partial_results.append(file_info)
                        # Check if we've reached the limit
                        if file_count[0] >= self.max_files:
                            break

            # Sort folders then files, based on natural sort (alpha, then num)
            return sorted(folders, key=natural_sort_file) + sorted(
                files, key=natural_sort_file
            )

        return recurse(self.directory) or []
