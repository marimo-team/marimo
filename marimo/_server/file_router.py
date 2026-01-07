# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
import os
from pathlib import Path
from typing import Optional

from marimo import _loggers
from marimo._server.app_defaults import AppDefaults
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.files.path_validator import PathValidator
from marimo._server.models.files import FileInfo
from marimo._server.models.home import MarimoFile
from marimo._session.notebook import AppFileManager
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath

LOGGER = _loggers.marimo_logger()

# Some unique identifier for a file
MarimoFileKey = str


class AppFileRouter(abc.ABC):
    """Abstract class for routing files to an AppFileManager."""

    NEW_FILE: MarimoFileKey = "__new__"

    @property
    def directory(self) -> str | None:
        return None

    @staticmethod
    def infer(path: str) -> AppFileRouter:
        if os.path.isfile(path):
            LOGGER.debug("Routing to file %s", path)
            return AppFileRouter.from_filename(MarimoPath(path))
        if os.path.isdir(path):
            LOGGER.debug("Routing to directory %s", path)
            return AppFileRouter.from_directory(path)
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Path {path} is not a valid file or directory",
        )

    @staticmethod
    def from_filename(file: MarimoPath) -> AppFileRouter:
        files = [
            MarimoFile(
                name=file.relative_name,
                path=file.absolute_name,
                last_modified=file.last_modified,
            )
        ]
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def from_directory(directory: str) -> AppFileRouter:
        return LazyListOfFilesAppFileRouter(directory, include_markdown=False)

    @staticmethod
    def from_files(files: list[MarimoFile]) -> AppFileRouter:
        return ListOfFilesAppFileRouter(files)

    @staticmethod
    def new_file() -> AppFileRouter:
        return NewFileAppFileRouter()

    def get_single_app_file_manager(
        self,
        defaults: Optional[AppDefaults] = None,
    ) -> AppFileManager:
        key = self.get_unique_file_key()
        assert key is not None, "Expected a single file"
        return self.get_file_manager(key, defaults)

    def get_file_manager(
        self,
        key: MarimoFileKey,
        defaults: Optional[AppDefaults] = None,
    ) -> AppFileManager:
        """
        Given a key, return an AppFileManager.
        """
        defaults = defaults or AppDefaults()

        if key.startswith(AppFileRouter.NEW_FILE):
            return AppFileManager(None, defaults=defaults)

        if os.path.exists(key):
            return AppFileManager(key, defaults=defaults)

        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"File {key} not found",
        )

    @abc.abstractmethod
    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        """
        If there is a unique file key, return it. Otherwise, return None.
        """
        pass

    @abc.abstractmethod
    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        """
        If there is a single file, return it. Otherwise, return None.
        """
        pass

    @property
    @abc.abstractmethod
    def files(self) -> list[FileInfo]:
        """
        Get all files in a recursive tree.
        """
        pass


class NewFileAppFileRouter(AppFileRouter):
    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        return AppFileRouter.NEW_FILE

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        return None

    @property
    def files(self) -> list[FileInfo]:
        return []


class ListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, files: list[MarimoFile]) -> None:
        self._files = files

    @property
    def files(self) -> list[FileInfo]:
        return [
            FileInfo(
                id=file.path,
                name=file.name,
                path=file.path,
                last_modified=file.last_modified,
                is_directory=False,
                is_marimo_file=True,
            )
            for file in self._files
        ]

    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        if len(self.files) == 1:
            return self.files[0].path
        return None

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        if len(self.files) == 1:
            file = self.files[0]
            return MarimoFile(
                name=file.name,
                path=file.path,
                last_modified=file.last_modified,
            )
        return None


class LazyListOfFilesAppFileRouter(AppFileRouter):
    def __init__(self, directory: str, include_markdown: bool) -> None:
        # Make directory absolute but don't resolve symlinks to preserve user paths
        abs_directory = Path(directory).absolute()
        self._directory = str(abs_directory)
        self.include_markdown = include_markdown
        self._lazy_files: Optional[list[FileInfo]] = None

        # Use PathValidator for security validation
        self._validator = PathValidator(abs_directory)
        # Use DirectoryScanner for file discovery (use absolute path)
        self._scanner = DirectoryScanner(str(abs_directory), include_markdown)

    @property
    def directory(self) -> str:
        return self._directory

    def toggle_markdown(
        self, include_markdown: bool
    ) -> LazyListOfFilesAppFileRouter:
        # Only create a new instance if the include_markdown flag is different
        if include_markdown != self.include_markdown:
            return LazyListOfFilesAppFileRouter(
                self.directory, include_markdown
            )
        return self

    def mark_stale(self) -> None:
        self._lazy_files = None

    def register_temp_dir(self, temp_dir: str) -> None:
        """Register a temp directory as allowed for file access.

        Args:
            temp_dir: The absolute path to the temp directory to allow.
        """
        self._validator.register_temp_dir(temp_dir)

    def is_file_in_allowed_temp_dir(self, filepath: str) -> bool:
        """Check if a file is inside an allowed temp directory.

        Args:
            filepath: The file path to check.

        Returns:
            True if the file is in an allowed temp directory, False otherwise.
        """
        return self._validator.is_file_in_allowed_temp_dir(filepath)

    def get_file_manager(
        self,
        key: MarimoFileKey,
        defaults: Optional[AppDefaults] = None,
    ) -> AppFileManager:
        """
        Given a key, return an AppFileManager.

        For directory sources, if the key is a relative path, resolve it
        relative to the source's directory. Absolute paths must be within
        the source's directory for security.
        """
        defaults = defaults or AppDefaults()

        if key.startswith(AppFileRouter.NEW_FILE):
            return AppFileManager(None, defaults=defaults)

        directory = Path(self._directory)
        filepath = Path(key)

        # Resolve filepath for use
        # If filepath is relative, resolve it relative to directory
        if not filepath.is_absolute():
            filepath = directory / filepath

        # Use PathValidator for security validation
        # Check if file is in an allowed temp directory (e.g., for tutorials)
        # If so, skip the directory validation
        is_in_allowed_temp_dir = self._validator.is_file_in_allowed_temp_dir(
            str(filepath)
        )

        if not is_in_allowed_temp_dir:
            # Validate that filepath is inside directory
            self._validator.validate_inside_directory(directory, filepath)

        if filepath.exists():
            return AppFileManager(str(filepath), defaults=defaults)

        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"File {key} not found",
        )

    @property
    def files(self) -> list[FileInfo]:
        if self._lazy_files is None:
            try:
                # Use DirectoryScanner to load files
                self._lazy_files = self._scanner.scan()
            except HTTPException as e:
                if e.status_code == HTTPStatus.REQUEST_TIMEOUT:
                    # Return partial results on timeout
                    LOGGER.warning(
                        "Timeout during file scan, returning partial results"
                    )
                    self._lazy_files = self._scanner.partial_results
                else:
                    raise
        return self._lazy_files

    def get_unique_file_key(self) -> str | None:
        return None

    def maybe_get_single_file(self) -> MarimoFile | None:
        return None


# Count total marimo files (not directories)
def count_files(file_list: list[FileInfo]) -> int:
    count = 0
    for item in file_list:
        if not item.is_directory:
            count += 1
        if item.children:
            count += count_files(item.children)
    return count
