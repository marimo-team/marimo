# Copyright 2024 Marimo. All rights reserved.
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
