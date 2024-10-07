# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import List

from marimo._runtime.packages.module_name_to_conda_name import (
    module_name_to_conda_name,
)
from marimo._runtime.packages.package_manager import (
    CanonicalizingPackageManager,
    PackageDescription,
)
from marimo._runtime.packages.utils import split_packages


class CondaPackageManager(CanonicalizingPackageManager):
    name = "conda"
    docs_url = "https://docs.conda.io/projects/conda/"

    def _construct_module_name_mapping(self) -> dict[str, str]:
        return module_name_to_conda_name()


class PixiPackageManager(CondaPackageManager):
    name = "pixi"

    async def _install(self, package: str) -> bool:
        return self.run(["pixi", "add", *split_packages(package)])

    async def uninstall(self, package: str) -> bool:
        return self.run(["pixi", "remove", *split_packages(package)])

    def list_packages(self) -> List[PackageDescription]:
        import json
        import subprocess

        if not self.is_manager_installed():
            return []

        try:
            proc = subprocess.run(
                ["pixi", "list", "--json"],
                capture_output=True,
                text=True,
                check=True,
            )
            packages = json.loads(proc.stdout)
            return [
                PackageDescription(name=pkg["name"], version=pkg["version"])
                for pkg in packages
            ]
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return []
