# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._runtime.packages.conda_package_manager import PixiPackageManager
from marimo._runtime.packages.package_manager import PackageManager
from marimo._runtime.packages.pypi_package_manager import (
    MicropipPackageManager,
    PipPackageManager,
    PoetryPackageManager,
    RyePackageManager,
    UvPackageManager,
)


@pytest.mark.parametrize(
    ("manager", "prefix", "suffix"),
    [
        (
            PipPackageManager(python_exe="/python"),
            ["/python", "-m", "pip", "install"],
            [],
        ),
        (
            UvPackageManager.for_pip_install("/python"),
            ["uv", "pip", "install"],
            ["-p", "/python"],
        ),
        (RyePackageManager(), ["rye", "add"], []),
        (PoetryPackageManager(), ["poetry", "add", "--no-interaction"], []),
        (PixiPackageManager(), ["pixi", "add"], []),
    ],
)
async def test_install_batch_preserves_arguments_and_tracks_attempts(
    manager: PackageManager, prefix: list[str], suffix: list[str]
) -> None:
    requirements = [
        "/tmp/local wheels/package.whl",
        'package[extra]>=1; python_version >= "3.10"',
        "other @ https://example.org/wheel.whl?value=a,b",
    ]
    if isinstance(manager, UvPackageManager):
        manager.__dict__["_uv_bin"] = "uv"
    assert manager.install_command(requirements, upgrade=False) == [
        *prefix,
        *requirements,
        *suffix,
    ]
    callback = MagicMock()
    with patch.object(manager, "_install", return_value=False) as install:
        assert not await manager.install_many(
            requirements, log_callback=callback
        )
    install.assert_awaited_once_with(
        requirements, upgrade=False, group=None, log_callback=callback
    )
    assert all(manager.attempted_to_install(req) for req in requirements)


@pytest.mark.parametrize(
    ("manager", "command"),
    [
        (
            PipPackageManager(python_exe="/python"),
            ["/python", "-m", "pip", "uninstall", "-y", "one", "two"],
        ),
        (
            UvPackageManager.for_pip_install("/python"),
            ["uv", "pip", "uninstall", "one", "two", "-p", "/python"],
        ),
        (RyePackageManager(), ["rye", "remove", "one", "two"]),
        (
            PoetryPackageManager(),
            ["poetry", "remove", "--no-interaction", "one", "two"],
        ),
        (PixiPackageManager(), ["pixi", "remove", "one", "two"]),
    ],
)
async def test_uninstall_batch_uses_one_command(
    manager: PackageManager, command: list[str]
) -> None:
    if isinstance(manager, UvPackageManager):
        manager.__dict__["_uv_bin"] = "uv"
    with patch.object(manager, "run", return_value=False) as run:
        assert not await manager.uninstall_many(["one", "two"])
    run.assert_awaited_once_with(command, log_callback=None)


@pytest.mark.parametrize("upgrade", [True, False])
async def test_micropip_batch_uses_list_api(upgrade: bool) -> None:
    manager = MicropipPackageManager()
    micropip = MagicMock()
    micropip.install = AsyncMock()
    requirements = ["one[extra]>=1", "two"]
    with (
        patch(
            "marimo._runtime.packages.pypi_package_manager.is_pyodide",
            return_value=True,
        ),
        patch.dict(sys.modules, {"micropip": micropip}),
    ):
        assert await manager.install_many(requirements, upgrade=upgrade)
        if upgrade:
            micropip.uninstall.assert_called_once_with(requirements)
            micropip.uninstall.reset_mock()
        assert await manager.uninstall_many(["one", "two"])
    micropip.install.assert_awaited_once_with(requirements)
    micropip.uninstall.assert_called_once_with(["one", "two"])
    assert all(manager.attempted_to_install(req) for req in requirements)


async def test_empty_batch_does_not_invoke_manager() -> None:
    manager = PipPackageManager()
    with (
        patch.object(manager, "_install") as install,
        patch.object(manager, "uninstall") as uninstall,
    ):
        assert await manager.install_many([])
        assert await manager.uninstall_many([])
    install.assert_not_called()
    uninstall.assert_not_called()
