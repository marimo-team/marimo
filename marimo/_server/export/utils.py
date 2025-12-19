# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Optional


def get_filename(filename: Optional[str], default: str = "notebook.py") -> str:
    if not filename:
        filename = default
    return filename


def get_download_filename(filename: Optional[str], extension: str) -> str:
    filename = filename or f"notebook.{extension}"
    basename = os.path.basename(filename)
    if basename.endswith(f".{extension}"):
        return basename
    return f"{os.path.splitext(basename)[0]}.{extension}"
