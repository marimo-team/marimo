# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._server.app_defaults import AppDefaults
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.files.path_validator import PathValidator
from marimo._server.models.files import FileInfo
from marimo._server.models.home import MarimoFile
from marimo._session.notebook import AppFileManager
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from collections.abc import Iterator

LOGGER = _loggers.marimo_logger()

# Some unique identifier for a file
MarimoFileKey = str


class AppFileRouter(abc.ABC):
    """Abstract class for routing files to an AppFileManager."""

    NEW_FILE: MarimoFileKey = "__new__"

    @property
    def directory(self) -> str | None:
        """Return the base directory for this router, or None if not directory-backed."""
        return None

    @staticmethod
    def infer(path: str) -> AppFileRouter:
        """Infer and return the appropriate router for the given file or directory path."""
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
        """Create a router for a single notebook file."""
        files = [
            MarimoFile(
                name=file.relative_name,
                path=file.absolute_name,
                last_modified=file.last_modified,
            )
        ]
        return ListOfFilesAppFileRouter(files, allow_dynamic=True)

    @staticmethod
    def from_directory(directory: str) -> AppFileRouter:
        """Create a lazy directory-scanning router rooted at the given directory."""
        return LazyListOfFilesAppFileRouter(directory, include_markdown=False)

    @staticmethod
    def from_files(
        files: list[MarimoFile],
        *,
        directory: str | None = None,
        allow_single_file_key: bool = True,
        allow_dynamic: bool = False,
    ) -> AppFileRouter:
        """Create a router from an explicit list of MarimoFile entries."""
        return ListOfFilesAppFileRouter(
            files,
            directory=directory,
            allow_single_file_key=allow_single_file_key,
            allow_dynamic=allow_dynamic,
        )

    @staticmethod
    def new_file() -> AppFileRouter:
        """Create a router for a new, unsaved notebook."""
        return NewFileAppFileRouter()

    def get_single_app_file_manager(
        self,
        defaults: Optional[AppDefaults] = None,
    ) -> AppFileManager:
        """Return the AppFileManager for the single file this router points to."""
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

    def resolve_file_path(self, key: MarimoFileKey) -> str | None:
        """Resolve a file key to an absolute file path, without loading the app.

        This is useful for endpoints that need file-backed resources (e.g. thumbnails)
        without the overhead of parsing/loading a notebook.

        Returns:
            Absolute file path if resolvable, otherwise None (e.g. new file).
        """
        if key.startswith(AppFileRouter.NEW_FILE):
            return None
        if os.path.exists(key):
            return key
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
    """AppFileRouter for a new (unsaved) file."""

    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        """Return the sentinel key for a new file."""
        return AppFileRouter.NEW_FILE

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        """Return None since there is no backing file."""
        return None

    @property
    def files(self) -> list[FileInfo]:
        """Return an empty file list."""
        return []


class ListOfFilesAppFileRouter(AppFileRouter):
    """AppFileRouter backed by an explicit list of MarimoFile entries."""

    def __init__(
        self,
        files: list[MarimoFile],
        directory: str | None = None,
        allow_single_file_key: bool = True,
        allow_dynamic: bool = False,
    ) -> None:
        self._files = files
        self._directory = directory
        self._allow_single_file_key = allow_single_file_key
        self._allow_dynamic = allow_dynamic
        self._allowed_paths = {
            str(normalize_path(Path(MarimoPath(file.path).absolute_name)))
            for file in files
        }

    @property
    def directory(self) -> str | None:
        """Return the base directory for this router."""
        return self._directory

    @property
    def files(self) -> list[FileInfo]:
        """Return FileInfo entries for all files in this router."""
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

    def get_file_manager(
        self,
        key: MarimoFileKey,
        defaults: Optional[AppDefaults] = None,
    ) -> AppFileManager:
        """Return an AppFileManager for the given key, resolving it against the allowed file list."""
        defaults = defaults or AppDefaults()

        resolved_path = self.resolve_file_path(key)
        if resolved_path is None:
            return AppFileManager(None, defaults=defaults)
        return AppFileManager(resolved_path, defaults=defaults)

    def resolve_file_path(self, key: MarimoFileKey) -> str | None:
        """Resolve a key to an absolute path, raising 404 if not in the allowed set."""
        if key.startswith(AppFileRouter.NEW_FILE):
            if self._allow_single_file_key:
                return None
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"File {key} not found",
            )

        filepath = Path(key)
        if not filepath.is_absolute() and self._directory:
            filepath = Path(self._directory) / filepath
        normalized_path = normalize_path(filepath)
        absolute_path = str(normalized_path)
        if absolute_path not in self._allowed_paths:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"File {key} not found",
            )

        if normalized_path.exists():
            return absolute_path

        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"File {key} not found",
        )

    def get_unique_file_key(self) -> Optional[MarimoFileKey]:
        """Return the unique file key when the router has exactly one file."""
        if self._allow_single_file_key and len(self._files) == 1:
            return self._files[0].path
        return None

    def maybe_get_single_file(self) -> Optional[MarimoFile]:
        """Return the single file when the router has exactly one file."""
        if self._allow_single_file_key and len(self._files) == 1:
            return self._files[0]
        return None

    def register_allowed_file(self, filepath: str) -> None:
        """Allow a file path in this router.

        This extends the allowlist for files that were not part of the original
        collection and may live outside the router's base directory (for
        example, files created at runtime in a separate location).
        """
        if not self._allow_dynamic:
            return
        self._allowed_paths.add(
            str(normalize_path(Path(MarimoPath(filepath).absolute_name)))
        )


class LazyListOfFilesAppFileRouter(AppFileRouter):
    """AppFileRouter that lazily scans a directory for marimo notebooks."""

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
        """Return the absolute path of the directory being scanned."""
        return self._directory

    def toggle_markdown(
        self, include_markdown: bool
    ) -> LazyListOfFilesAppFileRouter:
        """Return a new router with the markdown inclusion flag toggled, or self if unchanged."""
        # Only create a new instance if the include_markdown flag is different
        if include_markdown != self.include_markdown:
            return LazyListOfFilesAppFileRouter(
                self.directory, include_markdown
            )
        return self

    def mark_stale(self) -> None:
        """Invalidate the cached file list so it will be rescanned on next access."""
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
        resolved_path = self.resolve_file_path(key)
        if resolved_path is None:
            return AppFileManager(None, defaults=defaults)
        return AppFileManager(resolved_path, defaults=defaults)

    def resolve_file_path(self, key: MarimoFileKey) -> str | None:
        """Resolve a key to an absolute path within this router's directory."""
        if key.startswith(AppFileRouter.NEW_FILE):
            return None

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
            return str(filepath)

        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"File {key} not found",
        )

    @property
    def files(self) -> list[FileInfo]:
        """Return all marimo notebook files found by scanning this router's directory."""
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
        """Return None since a directory router does not have a unique file key."""
        return None

    def maybe_get_single_file(self) -> MarimoFile | None:
        """Return None since a directory router does not have a single file."""
        return None


# Count total marimo files (not directories)
def count_files(file_list: list[FileInfo]) -> int:
    """Recursively count non-directory FileInfo entries in the list."""
    count = 0
    for item in file_list:
        if not item.is_directory:
            count += 1
        if item.children:
            count += count_files(item.children)
    return count


def flatten_files(files: list[FileInfo]) -> Iterator[FileInfo]:
    """Iterate over files, skipping directories."""
    stack = files.copy()
    while stack:
        file = stack.pop()
        if file.is_directory:
            stack.extend(file.children)
        else:
            yield file
