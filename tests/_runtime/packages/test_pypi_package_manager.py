from __future__ import annotations

import json
import sys
from functools import partial
from unittest.mock import MagicMock, patch

from marimo._ast import compiler
from marimo._runtime.packages.pypi_package_manager import (
    PackageDescription,
    PipPackageManager,
    UvPackageManager,
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
        ["pip", "--python", PY_EXE, "install", "package1", "package2"],
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
            "--python",
            PY_EXE,
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
        ["pip", "--python", PY_EXE, "list", "--format=json"],
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


# UV Package Manager Tests


@patch.dict("os.environ", {}, clear=True)
def test_uv_is_in_uv_project_no_venv():
    """Test is_in_uv_project returns False when no VIRTUAL_ENV is set"""
    mgr = UvPackageManager()
    assert mgr.is_in_uv_project is False


@patch.dict("os.environ", {"VIRTUAL_ENV": "/path/to/venv"}, clear=True)
def test_uv_is_in_uv_project_no_uv_env():
    """Test is_in_uv_project returns False when UV env var is not set"""
    mgr = UvPackageManager()
    assert mgr.is_in_uv_project is False


@patch.dict(
    "os.environ",
    {"VIRTUAL_ENV": "/path/to/venv", "UV": "/other/path"},
    clear=True,
)
def test_uv_is_in_uv_project_uv_env_mismatch():
    """Test is_in_uv_project returns False when UV env var doesn't match VIRTUAL_ENV"""
    mgr = UvPackageManager()
    assert mgr.is_in_uv_project is False


@patch.dict(
    "os.environ",
    {"VIRTUAL_ENV": "/path/to/venv", "UV": "/path/to/venv"},
    clear=True,
)
@patch("pathlib.Path.exists")
def test_uv_is_in_uv_project_missing_files(mock_exists: MagicMock):
    """Test is_in_uv_project returns False when uv.lock or pyproject.toml don't exist"""
    mock_exists.return_value = False
    mgr = UvPackageManager()
    assert mgr.is_in_uv_project is False


@patch.dict(
    "os.environ",
    {"VIRTUAL_ENV": "/path/to/venv", "UV": "/path/to/venv"},
    clear=True,
)
@patch("pathlib.Path.exists")
def test_uv_is_in_uv_project_true(mock_exists: MagicMock):
    """Test is_in_uv_project returns True when all conditions are met"""
    mock_exists.return_value = True
    mgr = UvPackageManager()
    assert mgr.is_in_uv_project is True


@patch.dict(
    "os.environ",
    {"VIRTUAL_ENV": "/path/to/venv", "UV": "/path/to/venv"},
    clear=True,
)
@patch("pathlib.Path.exists")
def test_uv_is_in_uv_project_cached(mock_exists: MagicMock):
    """Test is_in_uv_project is cached and only evaluates once"""
    mock_exists.return_value = True
    mgr = UvPackageManager()

    # Access the property multiple times
    result1 = mgr.is_in_uv_project
    result2 = mgr.is_in_uv_project
    result3 = mgr.is_in_uv_project

    # Should all return the same value
    assert result1 is True
    assert result2 is True
    assert result3 is True

    # Path.exists should only be called twice (once for uv.lock, once for pyproject.toml)
    # since the property is cached after the first access
    assert mock_exists.call_count == 2


@patch("subprocess.run")
@patch.object(UvPackageManager, "is_in_uv_project", False)
async def test_uv_install_not_in_project(mock_run: MagicMock):
    """Test UV install uses pip subcommand when not in UV project"""
    mock_run.return_value = MagicMock(returncode=0)
    mgr = UvPackageManager()

    result = await mgr._install("package1 package2")

    mock_run.assert_called_once_with(
        [
            "uv",
            "pip",
            "install",
            "--compile",
            "package1",
            "package2",
            "-p",
            PY_EXE,
        ],
    )
    assert result is True


@patch("subprocess.run")
@patch.object(UvPackageManager, "is_in_uv_project", True)
async def test_uv_install_in_project(mock_run: MagicMock):
    """Test UV install uses add subcommand when in UV project"""
    mock_run.return_value = MagicMock(returncode=0)
    mgr = UvPackageManager()

    result = await mgr._install("package1 package2")

    mock_run.assert_called_once_with(
        ["uv", "add", "--compile", "package1", "package2", "-p", PY_EXE],
    )
    assert result is True


@patch("subprocess.run")
@patch.object(UvPackageManager, "is_in_uv_project", False)
async def test_uv_uninstall_not_in_project(mock_run: MagicMock):
    """Test UV uninstall uses pip subcommand when not in UV project"""
    mock_run.return_value = MagicMock(returncode=0)
    mgr = UvPackageManager()

    result = await mgr.uninstall("package1 package2")

    mock_run.assert_called_once_with(
        ["uv", "pip", "uninstall", "package1", "package2", "-p", PY_EXE],
    )
    assert result is True


@patch("subprocess.run")
@patch.object(UvPackageManager, "is_in_uv_project", True)
async def test_uv_uninstall_in_project(mock_run: MagicMock):
    """Test UV uninstall uses remove subcommand when in UV project"""
    mock_run.return_value = MagicMock(returncode=0)
    mgr = UvPackageManager()

    result = await mgr.uninstall("package1 package2")

    mock_run.assert_called_once_with(
        ["uv", "remove", "package1", "package2", "-p", PY_EXE],
    )
    assert result is True


@patch("subprocess.run")
def test_uv_list_packages(mock_run: MagicMock):
    """Test UV list packages uses pip list subcommand"""
    mock_output = json.dumps(
        [
            {"name": "package1", "version": "1.0.0"},
            {"name": "package2", "version": "2.1.0"},
        ]
    )
    mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
    mgr = UvPackageManager()

    packages = mgr.list_packages()

    mock_run.assert_called_once_with(
        ["uv", "pip", "list", "--format=json", "-p", PY_EXE],
        capture_output=True,
        text=True,
    )
    assert len(packages) == 2
    assert packages[0] == PackageDescription(name="package1", version="1.0.0")
    assert packages[1] == PackageDescription(name="package2", version="2.1.0")
