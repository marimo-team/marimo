# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.abc import Traversable


def import_files(filename: str) -> Traversable:
    from importlib.resources import files as importlib_files

    return importlib_files(filename)


def marimo_package_path() -> Path:
    return Path(str(import_files("marimo")))


def pretty_path(filename: str) -> str:
    """
    If it's an absolute path, shorten to relative path if
    we don't go outside the current directory.
    Otherwise, return the filename as is.
    """
    if os.path.isabs(filename):
        try:
            relpath = os.path.relpath(filename)
        except ValueError:
            # Windows: relpath doesn't work if filename is on a different drive
            # than current drive
            return filename
        if not relpath.startswith(".."):
            return relpath
    return filename


def maybe_make_dirs(filepath: Path) -> None:
    """
    Create directories if they don't exist.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)


def normalize_path(path: Path) -> Path:
    """Normalize a path without resolving symlinks.

    This function:
    - Converts relative paths to absolute paths
    - Normalizes .. and . components
    - Does NOT resolve symlinks (unlike Path.resolve())

    Args:
        path: The path to normalize

    Returns:
        Normalized absolute path without symlink resolution

    Example:
        >>> normalize_path(Path("foo/../bar"))
        Path("/current/working/dir/bar")
    """
    # Make absolute if relative (relative to current working directory)
    if not path.is_absolute():
        path = Path.cwd() / path

    # Use os.path.normpath to normalize .. and . without resolving symlinks
    normalized = Path(os.path.normpath(str(path)))

    return normalized
