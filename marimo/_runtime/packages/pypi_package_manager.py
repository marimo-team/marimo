# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import subprocess
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
        if not import_namespaces_to_add and not import_namespaces_to_remove:
            return

        # Convert from module name to package name
        packages_to_add = [
            self.module_to_package(im) for im in import_namespaces_to_add
        ]
        packages_to_remove = [
            self.module_to_package(im) for im in import_namespaces_to_remove
        ]

        version_map = self._get_version_map()

        def _is_installed(package: str) -> bool:
            return package.lower() in version_map

        def _maybe_add_version(package: str) -> str:
            # Skip marimo
            if package == "marimo":
                return package
            version = version_map.get(package.lower())
            if version:
                return f"{package}=={version}"
            return package

        # Filter to packages that are found in "uv pip list"
        packages_to_add = [
            _maybe_add_version(im)
            for im in packages_to_add
            if _is_installed(im)
        ]

        packages_to_remove = [
            im for im in packages_to_remove if _is_installed(im)
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

    def _get_version_map(self) -> dict[str, str]:
        cmd = ["uv", "pip", "list", "--format=json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return {}
        try:
            packages = json.loads(proc.stdout)
            return {pkg["name"]: pkg["version"] for pkg in packages}
        except json.JSONDecodeError:
            return {}


class RyePackageManager(PypiPackageManager):
    name = "rye"

    async def _install(self, package: str) -> bool:
        return self.run(["rye", "add", package])


class PoetryPackageManager(PypiPackageManager):
    name = "poetry"

    async def _install(self, package: str) -> bool:
        return self.run(["poetry", "add", package])
