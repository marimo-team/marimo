# Copyright 2024 Marimo. All rights reserved.
import sys
from typing import Any


def import_files(filename: str) -> Any:
    if sys.version_info < (3, 9):
        from importlib_resources import files as importlib_files
    else:
        from importlib.resources import files as importlib_files

    return importlib_files(filename)
