# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import Optional

from marimo import _loggers
from marimo._utils.http import HTTPException, HTTPStatus

LOGGER = _loggers.marimo_logger()


class PathValidator:
    """Validates file paths for security and access control.

    Handles:
    - Directory containment validation (prevent path traversal)
    - Temporary directory allowlisting (for tutorials)
    - Symlink resolution and security
    """

    def __init__(self, base_directory: Optional[Path] = None):
        """Initialize PathValidator.

        Args:
            base_directory: The base directory to validate paths against.
                           If None, validation is skipped.
        """
        self.base_directory = base_directory
        self._allowed_temp_dirs: set[Path] = set()

    def register_temp_dir(self, temp_dir: str) -> None:
        """Register a temp directory as allowed for file access.

        Args:
            temp_dir: The absolute path to the temp directory to allow.
        """
        # Normalize the path to ensure consistency
        normalized_path = Path(temp_dir).resolve()
        self._allowed_temp_dirs.add(normalized_path)
        LOGGER.debug("Registered allowed temp directory: %s", normalized_path)

    def is_file_in_allowed_temp_dir(self, filepath: str) -> bool:
        """Check if a file is inside an allowed temp directory.

        Args:
            filepath: The file path to check.

        Returns:
            True if the file is in an allowed temp directory, False otherwise.
        """
        if not self._allowed_temp_dirs:
            return False

        try:
            file_resolved = Path(filepath).resolve(strict=False)
            for temp_dir in list(self._allowed_temp_dirs):
                try:
                    file_resolved.relative_to(temp_dir)
                    return True
                except ValueError:
                    # Not a child of this temp directory, try next
                    continue
            return False
        except Exception as e:
            LOGGER.warning(
                "Error checking if file %s is in allowed temp dir: %s",
                filepath,
                e,
            )
            return False

    def validate_inside_directory(
        self, directory: Path, filepath: Path
    ) -> None:
        """
        Validate that a filepath is inside a directory.

        Handles all combinations of absolute/relative paths for both directory
        and filepath. Resolves symlinks and prevents path traversal attacks.

        Args:
            directory: The directory path (can be absolute or relative)
            filepath: The file path to validate (can be absolute or relative)

        Raises:
            HTTPException: If the filepath is outside the directory or if there's
                an error resolving paths (e.g., broken symlinks, permission errors)
        """
        try:
            # Handle empty paths - Path("") resolves to ".", so check for that
            if str(directory) == "." and str(filepath) == ".":
                # Both are current directory - this is ambiguous
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="Empty or ambiguous directory or filepath provided",
                )

            # Resolve directory to absolute path
            # If directory is relative, resolve it relative to current working directory
            directory_resolved = directory.resolve(strict=False)

            # If directory doesn't exist, we can't validate - this is an error
            if not directory_resolved.exists():
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Directory {directory} does not exist",
                )

            if not directory_resolved.is_dir():
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Path {directory} is not a directory",
                )

            # Resolve filepath to absolute path
            # If directory is absolute and filepath is relative, resolve relative to directory
            # (matches behavior in get_file_manager)
            # Otherwise, resolve relative to current working directory
            if not filepath.is_absolute() and directory_resolved.is_absolute():
                # Resolve relative filepath relative to the directory
                filepath_resolved = (directory_resolved / filepath).resolve(
                    strict=False
                )
            elif filepath.is_absolute():
                # Absolute filepath - resolve it directly (resolves symlinks)
                filepath_resolved = filepath.resolve(strict=False)
            else:
                # Both are relative - resolve relative to current working directory
                filepath_resolved = filepath.resolve(strict=False)

            # Check if filepath is inside directory
            # Use resolve() to handle symlinks and normalize paths
            try:
                # Ensure both paths are fully resolved (handles symlinks)
                # resolve(strict=False) resolves symlinks even if final path doesn't exist
                filepath_absolute = filepath_resolved.resolve(strict=False)
                directory_absolute = directory_resolved.resolve(strict=False)

                # A directory is not inside itself
                if filepath_absolute == directory_absolute:
                    raise HTTPException(
                        status_code=HTTPStatus.FORBIDDEN,
                        detail=f"Access denied: File {filepath} is the same as directory {directory}",
                    )

                # Check if filepath is inside directory using relative_to
                # This prevents path traversal attacks
                try:
                    filepath_absolute.relative_to(directory_absolute)
                except ValueError:
                    # filepath is not inside directory
                    raise HTTPException(
                        status_code=HTTPStatus.FORBIDDEN,
                        detail=f"Access denied: File {filepath} is outside the allowed directory {directory}",
                    ) from None

            except OSError as e:
                # Handle errors like broken symlinks, permission errors, etc.
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Error resolving path {filepath}: {str(e)}",
                ) from e

        except HTTPException:
            # Re-raise HTTPException as-is
            raise
        except Exception as e:
            # Catch any other unexpected errors
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail=f"Unexpected error validating path: {str(e)}",
            ) from e

    def validate_file_access(self, filepath: Path) -> None:
        """Validate file can be accessed (combines checks).

        Checks if the file is in an allowed temp directory, and if not,
        validates it's inside the base directory.

        Args:
            filepath: The file path to validate

        Raises:
            HTTPException: If validation fails
        """
        if self.base_directory is None:
            return

        # Check if file is in an allowed temp directory first
        if self.is_file_in_allowed_temp_dir(str(filepath)):
            return

        # Otherwise, validate it's inside the base directory
        self.validate_inside_directory(self.base_directory, filepath)
