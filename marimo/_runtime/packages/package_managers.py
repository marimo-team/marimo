# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from marimo._environments.environment import Environment
    from marimo._environments.sandbox import Backend

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
    sandbox_backend: Backend | None = None,
    sandbox_environment: Environment | None = None,
) -> PackageManager:
    """Creates the named package manager.

    `script_path` selects the notebook sandbox package adapter: package
    changes edit the Manifest and synchronize its Environment through the
    selected backend instead of installing imperatively. The backend
    defaults to the one this process was sandboxed with.
    """
    if is_pyodide():
        # user config has name "pip", but micropip's name is "micropip" ...
        return MicropipPackageManager()

    if script_path is not None:
        from marimo._environments.backends import current_backend
        from marimo._environments.sandbox import NotebookSandbox
        from marimo._runtime.packages.sandbox_package_manager import (
            SandboxPackageManager,
        )

        return SandboxPackageManager(
            NotebookSandbox(
                script_path,
                sandbox_backend or current_backend(),
                environment=sandbox_environment,
            )
        )

    if name == UvPackageManager.name:
        return UvPackageManager(python_exe=python_exe)

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
