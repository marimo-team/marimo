# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.packages.module_name_to_conda_name import (
    module_name_to_conda_name,
)
from marimo._runtime.packages.package_manager import (
    CanonicalizingPackageManager,
)


class CondaPackageManager(CanonicalizingPackageManager):
    def _construct_module_name_mapping(self) -> dict[str, str]:
        return module_name_to_conda_name()


class PixiPackageManager(CondaPackageManager):
    name = "pixi"

    async def _install(self, package: str) -> bool:
        return self.run(["pixi", "add", package])
