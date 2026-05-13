# Copyright 2026 Marimo. All rights reserved.
"""Workspace that lazily scans a directory of notebooks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.files.path_validator import PathValidator
from marimo._server.workspace._base import (
    NEW_FILE,
    MarimoFileKey,
    NotebookWorkspace,
    file_not_found,
)
from marimo._utils.http import HTTPException, HTTPStatus

if TYPE_CHECKING:
    from marimo._server.models.files import FileInfo
    from marimo._server.models.home import MarimoFile

LOGGER = _loggers.marimo_logger()


class DirectoryWorkspace(NotebookWorkspace):
    """A workspace backed by a directory, scanned lazily on demand.

    Used by ``marimo edit ./`` and ``marimo run ./``. File access is validated
    via :class:`PathValidator` to ensure paths stay within the directory (or an
    explicitly registered temp directory).
    """

    def __init__(self, directory: str, include_markdown: bool) -> None:
        # Make absolute but don't resolve symlinks — preserve user paths.
        abs_directory = Path(directory).absolute()
        self._directory = str(abs_directory)
        self._include_markdown = include_markdown
        self._lazy_files: list[FileInfo] | None = None
        self._validator = PathValidator(abs_directory)
        self._scanner = DirectoryScanner(str(abs_directory), include_markdown)

    @property
    def directory(self) -> str:
        return self._directory

    @property
    def include_markdown(self) -> bool:
        return self._include_markdown

    def set_include_markdown(self, include_markdown: bool) -> None:
        """Toggle markdown inclusion in place; rescans on next access."""
        if include_markdown == self._include_markdown:
            return
        self._include_markdown = include_markdown
        self._scanner = DirectoryScanner(self._directory, include_markdown)
        self._lazy_files = None

    def invalidate(self) -> None:
        self._lazy_files = None

    def register_temp_dir(self, temp_dir: str) -> None:
        self._validator.register_temp_dir(temp_dir)

    def is_in_allowed_temp_dir(self, path: str) -> bool:
        return self._validator.is_file_in_allowed_temp_dir(path)

    def single_file(self) -> MarimoFile | None:
        return None

    def get_unique_file_key(self) -> MarimoFileKey | None:
        return None

    def resolve(self, key: MarimoFileKey) -> str | None:
        if key.startswith(NEW_FILE):
            return None

        directory = Path(self._directory)
        filepath = Path(key)

        # Resolve relative paths against the workspace directory.
        if not filepath.is_absolute():
            filepath = directory / filepath

        # Tutorial files live in registered temp dirs and bypass containment.
        if not self._validator.is_file_in_allowed_temp_dir(str(filepath)):
            self._validator.validate_inside_directory(directory, filepath)

        if filepath.exists():
            return str(filepath)

        raise file_not_found(key)

    @property
    def files(self) -> list[FileInfo]:
        if self._lazy_files is None:
            try:
                self._lazy_files = self._scanner.scan()
            except HTTPException as e:
                if e.status_code == HTTPStatus.REQUEST_TIMEOUT:
                    LOGGER.warning(
                        "Timeout during file scan, returning partial results"
                    )
                    self._lazy_files = self._scanner.partial_results
                else:
                    raise
        return self._lazy_files
