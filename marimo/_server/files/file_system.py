# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Optional

from marimo._server.models.files import FileDetailsResponse, FileInfo


class FileSystem(ABC):
    @abstractmethod
    def get_root(self) -> str:
        """Get the root path."""
        pass

    @abstractmethod
    def list_files(self, path: str) -> list[FileInfo]:
        """List files and directories in a given path."""
        pass

    @abstractmethod
    def get_details(
        self,
        path: str,
        encoding: str | None = None,
        contents: str | None = None,
    ) -> FileDetailsResponse:
        """Get details of a specific file or directory. If contents is provided, use it instead of reading from disk."""
        pass

    @abstractmethod
    def open_file(self, path: str) -> str:
        """Open and read the content of a file."""
        pass

    @abstractmethod
    def create_file_or_directory(
        self,
        path: str,
        file_type: Literal["file", "directory"],
        name: str,
        contents: Optional[bytes],
    ) -> FileInfo:
        """
        Create a new file or directory

        If the name already exists, a new name will be generated.
        """
        pass

    @abstractmethod
    def delete_file_or_directory(self, path: str) -> bool:
        """Delete a file or directory."""
        pass

    @abstractmethod
    def move_file_or_directory(self, path: str, new_path: str) -> FileInfo:
        """Rename or move a file or directory."""
        pass

    @abstractmethod
    def update_file(self, path: str, contents: str) -> FileInfo:
        """Update the contents of a file."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        path: Optional[str] = None,
        directory: Optional[bool] = None,
        file: Optional[bool] = None,
        depth: int = 3,
        limit: int = 100,
    ) -> list[FileInfo]:
        """Search for files and directories matching a query.

        Args:
            query: Search query string (matches file/directory names)
            path: Root path to search from (defaults to root)
            directory: Filter to only directories (optional)
            file: Filter to only files (optional)
            depth: Maximum depth to search (default: 3)
            limit: Maximum number of results to return (default: 100)
        """
        pass
