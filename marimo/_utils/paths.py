# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
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


MARIMO_DIR_NAME = "__marimo__"


def notebook_output_dir(notebook_path: Path | str | None) -> Path:
    """Compute the __marimo__ output directory for a given notebook.

    When ``sys.pycache_prefix`` is set and the notebook path is absolute, the
    directory tree is mirrored under the prefix (similar to how Python mirrors
    ``__pycache__`` directories).  Otherwise the ``__marimo__`` directory is
    placed next to the notebook file.

    Resolution order:
        1. ``sys.pycache_prefix`` (if set and path is absolute): mirror tree
        2. Default: ``<notebook_parent>/__marimo__``
        3. Fallback (``None`` path): ``__marimo__`` relative to CWD
    """
    if notebook_path is None:
        return Path(MARIMO_DIR_NAME)

    raw = Path(notebook_path)
    originally_absolute = raw.is_absolute()

    path = normalize_path(raw)
    # Determine the notebook's parent directory.
    if path.is_dir():
        parent = path
    elif path.suffix:
        parent = path.parent
    else:
        # Ambiguous (non-existing path without extension): assume directory.
        # marimo notebooks are expected to have a file extension.
        parent = path

    prefix = getattr(sys, "pycache_prefix", None)
    if prefix is not None and originally_absolute:
        # Strip the filesystem root so we can graft onto the prefix.
        # On Unix "/" -> parts[1:], on Windows "C:\\" -> parts[1:].
        relative = Path(*parent.parts[1:]) if len(parent.parts) > 1 else Path()
        return Path(prefix) / relative / MARIMO_DIR_NAME

    return parent / MARIMO_DIR_NAME


def is_cloudpath(path: Path) -> bool:
    """Check if a path is a cloudpathlib CloudPath (including subclasses).

    Uses a module-name heuristic first, then falls back to isinstance
    when cloudpathlib is already imported (to catch virtual subclasses
    registered via CloudPath.register()).
    """
    # Quick module-name heuristic — works without importing cloudpathlib.
    if path.__class__.__module__.startswith("cloudpathlib"):
        return True

    # If cloudpathlib hasn't been imported yet there's no way a virtual
    # subclass (CloudPath.register()) could exist, so skip the import.
    if "cloudpathlib" not in sys.modules:
        return False

    try:
        from cloudpathlib import CloudPath  # type: ignore[import-not-found] # noqa: I001

        return isinstance(path, CloudPath)
    except ImportError:
        return False


def normalize_path(path: Path) -> Path:
    """Normalize a path without resolving symlinks.

    This function:
    - Converts relative paths to absolute paths
    - Normalizes .. and . components
    - Does NOT resolve symlinks (unlike Path.resolve())
    - Skips normalization for cloud paths (e.g., S3Path, GCSPath, AzurePath)
      to avoid corrupting URI schemes like s3://

    Args:
        path: The path to normalize

    Returns:
        Normalized absolute path without symlink resolution

    Example:
        >>> normalize_path(Path("foo/../bar"))
        Path("/current/working/dir/bar")
    """
    # Skip normalization for cloud paths (e.g., S3Path, GCSPath, AzurePath)
    # os.path.normpath corrupts URI schemes like s3:// by reducing them to s3:/
    if is_cloudpath(path):
        return path

    # Make absolute if relative (relative to current working directory)
    if not path.is_absolute():
        path = Path.cwd() / path

    # Use os.path.normpath to normalize .. and . without resolving symlinks
    normalized = Path(os.path.normpath(str(path)))

    return normalized
