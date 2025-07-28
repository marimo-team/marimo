# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("marimo")
except PackageNotFoundError:
    # package is not installed
    __version__ = "unknown"
