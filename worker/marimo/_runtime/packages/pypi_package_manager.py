# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import subprocess

from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)
from marimo._runtime.packages.package_manager import PackageManager
from marimo._utils.platform import is_pyodide


class PypiPackageManager(PackageManager):
    """Base class for package managers that use PyPI.

    Has a heuristic for mapping from package names to module names and back,
    using a registry of well-known packages and basic rules for package
    names.
    """

    def __init__(self) -> None:
        # Initialized lazily
        self._module_name_to_pypi_name: dict[str, str] | None = None
        self._pypi_name_to_module_name: dict[str, str] | None = None

    def _initialize_mappings(self) -> None:
        if self._module_name_to_pypi_name is None:
            self._module_name_to_pypi_name = module_name_to_pypi_name()

        if self._pypi_name_to_module_name is None:
            self._pypi_name_to_module_name = {
                v: k for k, v in self._module_name_to_pypi_name.items()
            }

    def module_to_package(self, module_name: str) -> str:
        """Canonicalizes a module name to a package name on PyPI."""
        if self._module_name_to_pypi_name is None:
            self._initialize_mappings()
        assert self._module_name_to_pypi_name is not None

        if module_name in self._module_name_to_pypi_name:
            return self._module_name_to_pypi_name[module_name]
        else:
            return module_name.replace("_", "-")

    def package_to_module(self, package_name: str) -> str:
        """Canonicalizes a package name to a module name."""
        if self._pypi_name_to_module_name is None:
            self._initialize_mappings()
        assert self._pypi_name_to_module_name is not None

        return (
            self._pypi_name_to_module_name[package_name]
            if package_name in self._pypi_name_to_module_name
            else package_name.replace("-", "_")
        )


class PipPackageManager(PypiPackageManager):
    name = "pip"

    async def install(self, package: str) -> bool:
        return subprocess.run(["pip", "install", package]).returncode == 0


class MicropipPackageManager(PypiPackageManager):
    name = "micropip"

    def is_manager_installed(self) -> bool:
        return is_pyodide()

    async def install(self, package: str) -> bool:
        assert is_pyodide()
        import micropip  # type: ignore

        try:
            await micropip.install(package)
            return True
        except ValueError:
            return False


class UvPackageManager(PypiPackageManager):
    name = "uv"

    async def install(self, package: str) -> bool:
        return (
            subprocess.run(["uv", "pip", "install", package]).returncode == 0
        )


class RyePackageManager(PypiPackageManager):
    name = "rye"

    async def install(self, package: str) -> bool:
        return subprocess.run(["rye", "add", package]).returncode == 0


class PoetryPackageManager(PypiPackageManager):
    name = "poetry"

    async def install(self, package: str) -> bool:
        return subprocess.run(["poetry", "add", package]).returncode == 0


# Pixi actually uses Conda by default ... but the package-to-module
# resolution that we use for Pypi packages seems to work fine, so
# we subclass PypiPackageManager.
#
# Can change the base class if/when needed.
class PixiPackageManager(PypiPackageManager):
    name = "pixi"

    async def install(self, package: str) -> bool:
        return subprocess.run(["pixi", "add", package]).returncode == 0
