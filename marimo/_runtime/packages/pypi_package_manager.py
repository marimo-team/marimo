# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import subprocess
import sys
from typing import List

from marimo._runtime.packages.module_name_to_pypi_name import (
    module_name_to_pypi_name,
)
from marimo._runtime.packages.package_manager import (
    CanonicalizingPackageManager,
    PackageDescription,
)
from marimo._runtime.packages.utils import split_packages
from marimo._utils.platform import is_pyodide

PY_EXE = sys.executable


class PypiPackageManager(CanonicalizingPackageManager):
    def _construct_module_name_mapping(self) -> dict[str, str]:
        return module_name_to_pypi_name()

    def _list_packages_from_cmd(
        self, cmd: List[str]
    ) -> List[PackageDescription]:
        if not self.is_manager_installed():
            return []
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return []
        try:
            packages = json.loads(proc.stdout)
            return [
                PackageDescription(name=pkg["name"], version=pkg["version"])
                for pkg in packages
            ]
        except json.JSONDecodeError:
            return []


class PipPackageManager(PypiPackageManager):
    name = "pip"
    docs_url = "https://pip.pypa.io/"

    async def _install(self, package: str) -> bool:
        return self.run(
            ["pip", "--python", PY_EXE, "install", *split_packages(package)]
        )

    async def uninstall(self, package: str) -> bool:
        return self.run(
            [
                "pip",
                "--python",
                PY_EXE,
                "uninstall",
                "-y",
                *split_packages(package),
            ]
        )

    def list_packages(self) -> List[PackageDescription]:
        cmd = ["pip", "--python", PY_EXE, "list", "--format=json"]
        return self._list_packages_from_cmd(cmd)


class MicropipPackageManager(PypiPackageManager):
    name = "micropip"
    docs_url = "https://micropip.pyodide.org/"

    def should_auto_install(self) -> bool:
        return True

    def is_manager_installed(self) -> bool:
        return is_pyodide()

    async def _install(self, package: str) -> bool:
        assert is_pyodide()
        import micropip  # type: ignore

        try:
            await micropip.install(split_packages(package))
            return True
        except ValueError:
            return False

    async def uninstall(self, package: str) -> bool:
        assert is_pyodide()
        import micropip  # type: ignore

        try:
            micropip.uninstall(package)
            return True
        except ValueError:
            return False

    def list_packages(self) -> List[PackageDescription]:
        assert is_pyodide()
        import micropip  # type: ignore

        packages = [
            PackageDescription(name=pkg.name, version=pkg.version)
            for pkg in micropip.list()
        ]
        # micropip doesn't sort the packages
        return sorted(packages, key=lambda pkg: pkg.name)

    def check_available(self) -> bool:
        return is_pyodide()


class UvPackageManager(PypiPackageManager):
    name = "uv"
    docs_url = "https://docs.astral.sh/uv/"

    async def _install(self, package: str) -> bool:
        return self.run(
            ["uv", "pip", "install", *split_packages(package), "-p", PY_EXE]
        )

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
        packages = self.list_packages()
        return {pkg.name: pkg.version for pkg in packages}

    async def uninstall(self, package: str) -> bool:
        return self.run(
            ["uv", "pip", "uninstall", *split_packages(package), "-p", PY_EXE]
        )

    def list_packages(self) -> List[PackageDescription]:
        cmd = ["uv", "pip", "list", "--format=json", "-p", PY_EXE]
        return self._list_packages_from_cmd(cmd)


class RyePackageManager(PypiPackageManager):
    name = "rye"
    docs_url = "https://rye.astral.sh/"

    async def _install(self, package: str) -> bool:
        return self.run(["rye", "add", *split_packages(package)])

    async def uninstall(self, package: str) -> bool:
        return self.run(["rye", "remove", *split_packages(package)])

    def list_packages(self) -> List[PackageDescription]:
        cmd = ["rye", "list", "--format=json"]
        return self._list_packages_from_cmd(cmd)


class PoetryPackageManager(PypiPackageManager):
    name = "poetry"
    docs_url = "https://python-poetry.org/docs/"

    async def _install(self, package: str) -> bool:
        return self.run(
            ["poetry", "add", "--no-interaction", *split_packages(package)]
        )

    async def uninstall(self, package: str) -> bool:
        return self.run(
            ["poetry", "remove", "--no-interaction", *split_packages(package)]
        )

    def list_packages(self) -> List[PackageDescription]:
        cmd = ["poetry", "show", "--no-dev", "--format=json"]
        return self._list_packages_from_cmd(cmd)
