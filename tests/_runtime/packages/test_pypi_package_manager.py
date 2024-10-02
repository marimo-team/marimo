from __future__ import annotations

import json
import sys
from functools import partial
from unittest.mock import MagicMock, patch

from marimo._ast import compiler
from marimo._runtime.packages.pypi_package_manager import (
    PackageDescription,
    PipPackageManager,
)

parse_cell = partial(compiler.compile_cell, cell_id="0")

PY_EXE = sys.executable


def test_module_to_package() -> None:
    mgr = PipPackageManager()
    assert mgr.module_to_package("marimo") == "marimo"
    assert mgr.module_to_package("123_456_789") == "123-456-789"
    assert mgr.module_to_package("sklearn") == "scikit-learn"


def test_package_to_module() -> None:
    mgr = PipPackageManager()
    assert mgr.package_to_module("marimo") == "marimo"
    assert mgr.package_to_module("123-456-789") == "123_456_789"
    assert mgr.package_to_module("scikit-learn") == "sklearn"


async def test_failed_install_returns_false() -> None:
    mgr = PipPackageManager()
    # almost surely does not exist
    assert not await mgr.install("asdfasdfasdfasdfqwerty", version=None)


manager = PipPackageManager()


@patch("subprocess.run")
async def test_install(mock_run: MagicMock):
    mock_run.return_value = MagicMock(returncode=0)

    result = await manager._install("package1 package2")

    mock_run.assert_called_once_with(
        ["pip", f"--python {PY_EXE}", "install", "package1", "package2"],
    )
    assert result is True


@patch("subprocess.run")
async def test_install_failure(mock_run: MagicMock):
    mock_run.return_value = MagicMock(returncode=1)

    result = await manager._install("nonexistent-package")

    assert result is False


@patch("subprocess.run")
async def test_uninstall(mock_run: MagicMock):
    mock_run.return_value = MagicMock(returncode=0)

    result = await manager.uninstall("package1 package2")

    mock_run.assert_called_once_with(
        [
            "pip",
            f"--python {PY_EXE}",
            "uninstall",
            "-y",
            "package1",
            "package2",
        ],
    )
    assert result is True


@patch("subprocess.run")
def test_list_packages(mock_run: MagicMock):
    mock_output = json.dumps(
        [
            {"name": "package1", "version": "1.0.0"},
            {"name": "package2", "version": "2.1.0"},
        ]
    )
    mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

    packages = manager.list_packages()

    mock_run.assert_called_once_with(
        ["pip", f"--python {PY_EXE}", "list", "--format=json"],
        capture_output=True,
        text=True,
    )
    assert len(packages) == 2
    assert packages[0] == PackageDescription(name="package1", version="1.0.0")
    assert packages[1] == PackageDescription(name="package2", version="2.1.0")


@patch("subprocess.run")
def test_list_packages_failure(mock_run: MagicMock):
    mock_run.return_value = MagicMock(returncode=1)

    packages = manager.list_packages()

    assert len(packages) == 0
