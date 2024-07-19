# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)
from marimo._runtime.packages.package_manager import (
    CanonicalizingPackageManager,
)
from marimo._utils.platform import is_pyodide


class PypiPackageManager(CanonicalizingPackageManager):
    def _construct_module_name_mapping(self) -> dict[str, str]:
        return module_name_to_pypi_name()


class PipPackageManager(PypiPackageManager):
    name = "pip"

    async def _install(self, package: str) -> bool:
        return self.run(["pip", "install", package])


class MicropipPackageManager(PypiPackageManager):
    name = "micropip"

    def should_auto_install(self) -> bool:
        return True

    def is_manager_installed(self) -> bool:
        return is_pyodide()

    async def _install(self, package: str) -> bool:
        assert is_pyodide()
        import micropip  # type: ignore

        try:
            await micropip.install(package)
            return True
        except ValueError:
            return False


class UvPackageManager(PypiPackageManager):
    name = "uv"

    async def _install(self, package: str) -> bool:
        return self.run(["uv", "pip", "install", package])


class RyePackageManager(PypiPackageManager):
    name = "rye"

    async def _install(self, package: str) -> bool:
        return self.run(["rye", "add", package])


class PoetryPackageManager(PypiPackageManager):
    name = "poetry"

    async def _install(self, package: str) -> bool:
        return self.run(["poetry", "add", package])
