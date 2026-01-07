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
        normalized_path = self._normalize_path_without_resolving_symlinks(
            Path(temp_dir), Path.cwd()
        )
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
            file_normalized = self._normalize_path_without_resolving_symlinks(
                Path(filepath), Path.cwd()
            )
            for temp_dir in list(self._allowed_temp_dirs):
                try:
                    file_normalized.relative_to(temp_dir)
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

    def _normalize_path_without_resolving_symlinks(
        self, path: Path, base: Path
    ) -> Path:
        """Normalize a path without resolving symlinks.

        Makes the path absolute relative to base and normalizes .. components,
        but does NOT resolve symlinks.

        Args:
            path: The path to normalize
            base: The base directory for relative paths

        Returns:
            Normalized absolute path without symlink resolution
        """
        import os

        from marimo._utils.tmpdir import _convert_to_long_pathname

        # Make absolute relative to base if needed
        if not path.is_absolute():
            path = base / path

        # Use os.path.normpath to normalize .. and . without resolving symlinks
        # Then convert back to Path
        normalized = Path(os.path.normpath(str(path)))

        # On Windows, convert short (8.3) path names to long path names.
        # This handles cases where Path.cwd() returns short names like
        # "C:\Users\RUNNER~1\..." but Path.resolve() returns long names
        # like "C:\Users\runneradmin\...". Without this normalization,
        # two paths referring to the same location may fail containment checks.
        normalized = Path(_convert_to_long_pathname(str(normalized)))

        # Ensure the normalized path is still absolute. While normpath generally
        # preserves absoluteness, we enforce this invariant explicitly for safety.
        if not normalized.is_absolute():
            LOGGER.error(
                "Normalized path is not absolute: %s (original: %s, base: %s)",
                normalized,
                path,
                base,
            )
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Invalid path: normalized path is not absolute",
            )

        return normalized

    def _check_containment(
        self,
        directory_abs: Path,
        filepath_abs: Path,
        directory: Path,
        filepath: Path,
    ) -> None:
        """Check that filepath is inside directory."""
        if filepath_abs == directory_abs:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"Access denied: File {filepath} is the same as directory {directory}",
            )

        try:
            filepath_abs.relative_to(directory_abs)
        except ValueError:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"Access denied: File {filepath} is outside the allowed directory {directory}",
            ) from None

    def validate_inside_directory(
        self, directory: Path, filepath: Path
    ) -> None:
        """
        Validate that a filepath is inside a directory.

        Handles all combinations of absolute/relative paths for both directory
        and filepath. By default, symlinks are preserved.

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

            try:
                # Normalize without resolving symlinks
                directory_normalized = (
                    self._normalize_path_without_resolving_symlinks(
                        directory, Path.cwd()
                    )
                )

                # If it was an absolute directory, then the base is that directory
                # otherwise, the base is the current working directory
                if directory.is_absolute():
                    filepath_base = directory
                else:
                    filepath_base = Path.cwd()

                filepath_normalized = (
                    self._normalize_path_without_resolving_symlinks(
                        filepath, filepath_base
                    )
                )
                self._check_containment(
                    directory_normalized,
                    filepath_normalized,
                    directory,
                    filepath,
                )

            except OSError as e:
                # Handle errors like permission errors, etc.
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
