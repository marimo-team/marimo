# Copyright 2026 Marimo. All rights reserved.
"""Storage abstraction for notebook persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from marimo import _loggers
from marimo._utils.http import HTTPException, HTTPStatus

LOGGER = _loggers.marimo_logger()


class StorageInterface(Protocol):
    """Interface for storage operations."""

    def read(self, path: Path) -> str:
        """Read content from storage.

        Args:
            path: Path to read from

        Returns:
            File contents as string

        Raises:
            HTTPException: If read fails
        """
        ...

    def write(self, path: Path, content: str) -> None:
        """Write content to storage.

        Args:
            path: Path to write to
            content: Content to write

        Raises:
            HTTPException: If write fails
        """
        ...

    def exists(self, path: Path) -> bool:
        """Check if path exists in storage.

        Args:
            path: Path to check

        Returns:
            True if path exists, False otherwise
        """
        ...

    def rename(self, old_path: Path, new_path: Path) -> None:
        """Rename/move a file in storage.

        Args:
            old_path: Source path
            new_path: Destination path

        Raises:
            HTTPException: If rename fails
        """
        ...

    def is_same_path(self, path1: Path, path2: Path) -> bool:
        """Check if two paths refer to the same location.

        Args:
            path1: First path
            path2: Second path

        Returns:
            True if paths refer to same location
        """
        ...

    def get_absolute_path(self, path: Path) -> Path:
        """Get absolute path.

        Args:
            path: Path to make absolute

        Returns:
            Absolute path
        """
        ...

    def read_related_file(
        self, base_path: Path, relative_path: str
    ) -> Optional[str]:
        """Read a file relative to a base path.

        Used for reading CSS files, layout configs, etc.

        Args:
            base_path: Base path (typically the notebook path)
            relative_path: Relative path from base

        Returns:
            File contents or None if not found
        """
        ...


class FilesystemStorage(StorageInterface):
    """Filesystem-based storage implementation."""

    def read(self, path: Path) -> str:
        """Read file from filesystem."""
        path = _ensure_path(path)
        try:
            return path.read_text(encoding="utf-8")
        except Exception as err:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail=f"Failed to read file {path}",
            ) from err

    def write(self, path: Path, content: str) -> None:
        """Write file to filesystem."""
        # Ensure path is a Path object
        path = _ensure_path(path)
        self.ensure_parent_dirs(path)
        try:
            path.write_text(content, encoding="utf-8")
        except Exception as err:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail=f"Failed to save file {path}",
            ) from err

    def exists(self, path: Path) -> bool:
        """Check if path exists on filesystem."""
        # Ensure path is a Path object
        path = _ensure_path(path)
        return path.exists()

    def rename(self, old_path: Path, new_path: Path) -> None:
        """Rename file on filesystem."""
        # Ensure paths are Path objects
        old_path = _ensure_path(old_path)
        new_path = _ensure_path(new_path)
        self.ensure_parent_dirs(new_path)
        try:
            old_path.rename(new_path)
        except Exception as err:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail=f"Failed to rename from {old_path} to {new_path}",
            ) from err

    def ensure_parent_dirs(self, path: Path) -> None:
        """Create parent directories if they don't exist."""
        path = _ensure_path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            LOGGER.warning(
                f"Failed to create parent directories for {path}: {e}"
            )

    def is_same_path(self, path1: Path, path2: Path) -> bool:
        """Check if two paths refer to the same file."""
        path1 = _ensure_path(path1)
        path2 = _ensure_path(path2)
        try:
            return path1.resolve() == path2.resolve()
        except OSError as e:
            LOGGER.debug(f"Could not resolve paths {path1} and {path2}: {e}")
            try:
                return path1.absolute() == path2.absolute()
            except Exception as e2:
                LOGGER.debug(
                    f"Could not get absolute paths for {path1} and {path2}: {e2}"
                )
                return str(path1) == str(path2)

    def get_absolute_path(self, path: Path) -> Path:
        """Get absolute path, resolving symlinks."""
        path = _ensure_path(path)
        try:
            return path.resolve()
        except OSError as e:
            LOGGER.warning(f"Could not resolve path {path}: {e}")
            return path.absolute()

    def read_related_file(
        self, base_path: Path, relative_path: str
    ) -> Optional[str]:
        """Read a file relative to the base path.

        Args:
            base_path: Base notebook path
            relative_path: Relative path to the related file

        Returns:
            File contents or None if not found
        """
        filepath = Path(relative_path)

        # If not an absolute path, make it relative to base_path's directory
        if not filepath.is_absolute():
            filepath = base_path.parent / filepath

        if not filepath.exists():
            LOGGER.error("Related file %s does not exist", filepath)
            return None

        try:
            return filepath.read_text(encoding="utf-8")
        except OSError as e:
            LOGGER.warning(
                "Failed to open related file %s for reading: %s",
                filepath,
                str(e),
            )
            return None


def _ensure_path(path: str | Path) -> Path:
    """Ensure path is a Path object."""
    if not isinstance(path, Path):
        path = Path(path)
    return path
