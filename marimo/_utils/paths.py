# Copyright 2024 Marimo. All rights reserved.
import os
import sys
from typing import Any


def import_files(filename: str) -> Any:
    if sys.version_info < (3, 9):
        from importlib_resources import files as importlib_files
    else:
        from importlib.resources import files as importlib_files

    return importlib_files(filename)


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
