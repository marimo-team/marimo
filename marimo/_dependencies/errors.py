# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal


class ManyModulesNotFoundError(ModuleNotFoundError):
    """
    Raised when multiple modules are not found.
    """

    package_names: list[str]
    source: Literal["kernel", "server"]

    def __init__(
        self,
        package_names: list[str],
        msg: str,
        source: Literal["kernel", "server"] = "kernel",
    ) -> None:
        self.package_names = package_names
        self.source = source
        super().__init__(msg)
