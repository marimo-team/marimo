# Copyright 2024 Marimo. All rights reserved.
from abc import ABC, abstractmethod
from typing import List

from marimo._server.models.files import FileInfo


class FileSystem(ABC):
    @abstractmethod
    def get_root(self) -> str:
        """Get the root path."""
        pass

    @abstractmethod
    def list_files(self, path: str) -> List[FileInfo]:
        """List files and directories in a given path."""
        pass

    @abstractmethod
    def get_details(self, path: str) -> FileInfo:
        """Get details of a specific file or directory."""
        pass

    @abstractmethod
    def open_file(self, path: str) -> str:
        """Open and read the content of a file."""
        pass

    @abstractmethod
    def create_file_or_directory(
        self, path: str, file_type: str, name: str
    ) -> bool:
        """Create a new file or directory."""
        pass

    @abstractmethod
    def delete_file_or_directory(self, path: str) -> bool:
        """Delete a file or directory."""
        pass

    @abstractmethod
    def update_file_or_directory(self, path: str, new_path: str) -> bool:
        """Rename or move a file or directory."""
        pass
