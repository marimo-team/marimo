# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from marimo._server.models.files import FileDetailsResponse, FileInfo


class FileSystem(ABC):
    @abstractmethod
    def get_root(self) -> str:
        """Get the root path."""

    @abstractmethod
    def list_files(self, path: str) -> list[FileInfo]:
        """List files and directories in a given path."""

    @abstractmethod
    def get_info(self, path: str) -> FileInfo:
        """Get metadata without materializing file contents for a response."""

    @abstractmethod
    def get_details(
        self,
        path: str,
        encoding: str | None = None,
        contents: str | None = None,
        max_bytes: int | None = None,
    ) -> FileDetailsResponse:
        """Get file details and optionally bound content reads.

        If `contents` is provided, use it instead of reading from disk. If
        `max_bytes` is provided and disk content exceeds it, return metadata
        with `is_too_large=True` and no contents.
        """

    @abstractmethod
    def open_file(self, path: str, encoding: str | None = None) -> str | bytes:
        """Open and read the content of a file.

        Returns str for text files, bytes for binary files.
        """

    @abstractmethod
    def create_file_or_directory(
        self,
        path: str,
        file_type: Literal["file", "directory"],
        name: str,
        contents: bytes | None,
    ) -> FileInfo:
        """
        Create a new file or directory

        If the name already exists, a new name will be generated.
        """

    @abstractmethod
    def delete_file_or_directory(self, path: str) -> bool:
        """Delete a file or directory."""

    @abstractmethod
    def copy_file_or_directory(self, path: str, new_path: str) -> FileInfo:
        """Duplicate or copy a file or directory."""

    @abstractmethod
    def move_file_or_directory(self, path: str, new_path: str) -> FileInfo:
        """Rename or move a file or directory."""

    @abstractmethod
    def update_file(self, path: str, contents: str) -> FileInfo:
        """Update the contents of a file."""

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        path: str | None = None,
        include_directories: bool = True,
        include_files: bool = True,
        depth: int = 3,
        limit: int = 100,
    ) -> list[FileInfo]:
        """Search for files and directories matching a query.

        Args:
            query: Search query string (matches file/directory names)
            path: Root path to search from (defaults to root)
            include_directories: Include directories
            include_files: Include files
            depth: Maximum depth to search (default: 3)
            limit: Maximum number of results to return (default: 100)
        """
