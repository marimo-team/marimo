# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

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

    def install_command(
        self, package: str, *, upgrade: bool, group: Optional[str] = None
    ) -> list[str]:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        return [
            "pixi",
            "upgrade" if upgrade else "add",
            *split_packages(package),
        ]

    async def uninstall(
        self, package: str, group: Optional[str] = None
    ) -> bool:
        # The `group` parameter is accepted for interface compatibility, but is ignored.
        del group
        return await self.run(
            ["pixi", "remove", *split_packages(package)], log_callback=None
        )

    def list_packages(self) -> list[PackageDescription]:
        import json
        import subprocess

        if not self.is_manager_installed():
            return []

        try:
            proc = subprocess.run(
                ["pixi", "list", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            packages = json.loads(proc.stdout)
            return [
                PackageDescription(name=pkg["name"], version=pkg["version"])
                for pkg in packages
            ]
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return []
