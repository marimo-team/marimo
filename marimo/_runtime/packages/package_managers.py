# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.packages.conda_package_manager import PixiPackageManager
from marimo._runtime.packages.package_manager import PackageManager
from marimo._runtime.packages.pypi_package_manager import (
    MicropipPackageManager,
    PipPackageManager,
    PoetryPackageManager,
    RyePackageManager,
    UvPackageManager,
)
from marimo._utils.platform import is_pyodide

PACKAGE_MANAGERS = {
    MicropipPackageManager.name: MicropipPackageManager,
    PipPackageManager.name: PipPackageManager,
    RyePackageManager.name: RyePackageManager,
    UvPackageManager.name: UvPackageManager,
    PoetryPackageManager.name: PoetryPackageManager,
    PixiPackageManager.name: PixiPackageManager,
}


def create_package_manager(
    name: str,
    python_exe: str | None = None,
    script_path: str | None = None,
) -> PackageManager:
    """Creates the named package manager.

    `script_path` puts uv in script mode: package changes edit the
    notebook's metadata and synchronize its script environment instead of
    installing imperatively. Other managers ignore it.
    """
    if is_pyodide():
        # user config has name "pip", but micropip's name is "micropip" ...
        return MicropipPackageManager()

    if name == UvPackageManager.name:
        return UvPackageManager(python_exe=python_exe, script_path=script_path)

    if name in PACKAGE_MANAGERS:
        return PACKAGE_MANAGERS[name](  # type:ignore[abstract,no-any-return]
            python_exe=python_exe
        )
    raise RuntimeError(
        f"Unknown package manager {name}. "
        "This is a bug in marimo."
        "Please file an issue: "
        "https://github.com/marimo-team/marimo/issues"
    )
