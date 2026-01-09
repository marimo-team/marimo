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


def pretty_path(filename: str, base_dir: Path | str | None = None) -> str:
    """
    Make a path "pretty" by converting to relative if possible.

    Args:
        filename: The path to prettify
        base_dir: If provided, compute relative to this directory first.
                  Falls back to CWD-relative if file is outside base_dir.

    Returns:
        A shorter, more readable path when possible.
    """
    if not filename:
        return filename

    file_path = Path(filename)

    if base_dir is not None and file_path.is_relative_to(base_dir):
        return str(file_path.relative_to(base_dir))
    if file_path.is_absolute() and file_path.is_relative_to(Path.cwd()):
        return str(file_path.relative_to(Path.cwd()))

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
