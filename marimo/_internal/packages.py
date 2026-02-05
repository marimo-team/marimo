# Copyright 2026 Marimo. All rights reserved.
"""Internal API for package management."""

from marimo._runtime.packages.package_manager import (
    PackageDescription,
    PackageManager,
)
from marimo._runtime.packages.package_managers import create_package_manager

__all__ = [
    "PackageDescription",
    "PackageManager",
    "create_package_manager",
]
