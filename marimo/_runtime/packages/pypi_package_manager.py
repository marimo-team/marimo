# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import List

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

    def update_notebook_script_metadata(
        self,
        filepath: str,
        import_namespaces_to_add: List[str],
        import_namespaces_to_remove: List[str],
    ) -> None:
        # Convert from module name to package name
        packages_to_add = [
            self.module_to_package(im) for im in import_namespaces_to_add
        ]
        packages_to_remove = [
            self.module_to_package(im) for im in import_namespaces_to_remove
        ]

        # Filter to packages that are found by "uv pip show"
        packages_to_add = [
            im for im in packages_to_add if self._is_installed(im)
        ]
        packages_to_remove = [
            im for im in packages_to_remove if self._is_installed(im)
        ]

        if packages_to_add:
            self.run(
                ["uv", "--quiet", "add", "--script", filepath]
                + packages_to_add
            )
        if packages_to_remove:
            self.run(
                ["uv", "--quiet", "remove", "--script", filepath]
                + packages_to_remove
            )

    def _is_installed(self, package: str) -> bool:
        return self.run(["uv", "--quiet", "pip", "show", package])


class RyePackageManager(PypiPackageManager):
    name = "rye"

    async def _install(self, package: str) -> bool:
        return self.run(["rye", "add", package])


class PoetryPackageManager(PypiPackageManager):
    name = "poetry"

    async def _install(self, package: str) -> bool:
        return self.run(["poetry", "add", package])
