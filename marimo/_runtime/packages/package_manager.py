# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import subprocess

from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)
from marimo._utils.platform import is_pyodide


class PackageManager(abc.ABC):
    """Interface for a package manager that can install packages."""

    @abc.abstractmethod
    def module_to_package(self, module_name: str) -> str:
        """Canonicalizes a module name to a package name."""
        ...

    @abc.abstractmethod
    def package_to_module(self, package_name: str) -> str:
        """Canonicalizes a package name to a module name."""
        ...

    @abc.abstractmethod
    async def install(self, package: str) -> bool:
        """Attempt to install a package that makes this module available.

        Returns True if installation succeeded, else False.
        """
        ...
