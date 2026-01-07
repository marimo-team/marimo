from __future__ import annotations

import json
import subprocess
import sys
from functools import partial
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from marimo._ast import compiler
from marimo._runtime.packages.package_manager import PackageDescription
from marimo._runtime.packages.pypi_package_manager import (
    PipPackageManager,
    PoetryPackageManager,
    UvPackageManager,
)

if TYPE_CHECKING:
    from pathlib import Path

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

    with patch.object(manager, "is_manager_installed", return_value=True):
        result = await manager._install(
            "package1 package2", upgrade=False, group=None
        )

    mock_run.assert_called_once_with(
        ["pip", "--python", PY_EXE, "install", "package1", "package2"],
    )
    assert result is True


@patch("subprocess.run")
async def test_install_failure(mock_run: MagicMock):
    mock_run.return_value = MagicMock(returncode=1)

    result = await manager._install(
        "nonexistent-package", upgrade=False, group=None
    )

    assert result is False


@patch("subprocess.run")
async def test_uninstall(mock_run: MagicMock):
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(manager, "is_manager_installed", return_value=True):
        result = await manager.uninstall("package1 package2", group=None)

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

    with patch.object(manager, "is_manager_installed", return_value=True):
        packages = manager.list_packages()

    mock_run.assert_called_once_with(
        ["pip", "--python", PY_EXE, "list", "--format=json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert len(packages) == 2
    assert packages[0] == PackageDescription(name="package1", version="1.0.0")
    assert packages[1] == PackageDescription(name="package2", version="2.1.0")


@patch("subprocess.run")
def test_list_packages_failure(mock_run: MagicMock):
    mock_run.return_value = MagicMock(returncode=1)

    packages = manager.list_packages()

    assert len(packages) == 0


# Poetry Package Manager Tests


def test_poetry_generate_cmd_version_one():
    mgr = PoetryPackageManager()
    assert mgr._generate_list_packages_cmd(1) == [
        "poetry",
        "show",
        "--no-dev",
    ]


@patch("subprocess.run")
def test_poetry_generate_cmd_version_two_prefers_without_dev(
    mock_run: MagicMock,
):
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    mgr = PoetryPackageManager()

    cmd = mgr._generate_list_packages_cmd(2)

    assert cmd == ["poetry", "show", "--without", "dev"]
    mock_run.assert_called_once_with(
        ["poetry", "show", "--without", "dev"],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("subprocess.run")
def test_poetry_generate_cmd_version_two_falls_back_when_missing_group(
    mock_run: MagicMock,
):
    mock_run.return_value = MagicMock(
        returncode=1, stderr="Group(s) not found"
    )
    mgr = PoetryPackageManager()

    cmd = mgr._generate_list_packages_cmd(2)

    assert cmd == ["poetry", "show"]


@patch("subprocess.run")
def test_poetry_generate_cmd_default_for_other_versions(
    mock_run: MagicMock,
):
    mock_run.return_value = MagicMock(returncode=1, stderr="")
    mgr = PoetryPackageManager()

    cmd = mgr._generate_list_packages_cmd(3)

    assert cmd == ["poetry", "show"]


@patch("subprocess.run")
def test_poetry_list_packages_parses_output(mock_run: MagicMock):
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="Poetry (1.8.2)"),
        MagicMock(
            returncode=0,
            stdout="package-1    1.0.0\npackage-two    2.0.0\n",
        ),
    ]
    mgr = PoetryPackageManager()

    with patch.object(
        PoetryPackageManager, "is_manager_installed", return_value=True
    ):
        packages = mgr.list_packages()

    assert packages == [
        PackageDescription(name="package-1", version="1.0.0"),
        PackageDescription(name="package-two", version="2.0.0"),
    ]

    # Last subprocess call should be the list invocation with UTF-8 encoding
    cmd_args, cmd_kwargs = mock_run.call_args_list[-1]
    assert cmd_args[0] == ["poetry", "show", "--no-dev"]
    assert cmd_kwargs.get("encoding") == "utf-8"
    assert cmd_kwargs.get("text") is True


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


@patch("subprocess.Popen")
@patch.object(UvPackageManager, "is_in_uv_project", False)
async def test_uv_install_not_in_project(mock_popen: MagicMock):
    """Test UV install uses pip subcommand when not in UV project"""
    mock_process = MagicMock()
    mock_process.wait.return_value = 0
    mock_process.stdout.readline.return_value = b""
    mock_popen.return_value = mock_process
    mgr = UvPackageManager()

    result = await mgr._install("package1 package2", upgrade=False, group=None)

    mock_popen.assert_called_once_with(
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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=False,
        bufsize=0,
    )
    assert result is True


@patch("subprocess.Popen")
@patch.object(UvPackageManager, "is_in_uv_project", False)
async def test_uv_install_not_in_project_with_target(mock_popen: MagicMock):
    """Test UV install uses pip with target"""
    mock_process = MagicMock()
    mock_process.wait.return_value = 0
    mock_process.stdout.readline.return_value = b""
    mock_popen.return_value = mock_process
    mgr = UvPackageManager()

    # Explicitly set environ, since patch doesn't work in an asynchronous
    # context.
    import os

    os.environ["MARIMO_UV_TARGET"] = "target_path"
    result = await mgr._install("package1 package2", upgrade=False, group=None)
    del os.environ["MARIMO_UV_TARGET"]

    mock_popen.assert_called_once_with(
        [
            "uv",
            "pip",
            "install",
            "--target=target_path",
            "--compile",
            "package1",
            "package2",
            "-p",
            PY_EXE,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=False,
        bufsize=0,
    )
    assert result is True


@patch("subprocess.run")
@patch.object(UvPackageManager, "is_in_uv_project", True)
async def test_uv_install_in_project(mock_run: MagicMock):
    """Test UV install uses add subcommand when in UV project"""
    mock_run.return_value = MagicMock(returncode=0)
    mgr = UvPackageManager()

    result = await mgr._install("package1 package2", upgrade=False, group=None)

    mock_run.assert_called_once_with(
        ["uv", "add", "--compile", "package1", "package2", "-p", PY_EXE],
    )
    assert result is True


@patch("subprocess.run")
@patch.object(UvPackageManager, "is_in_uv_project", True)
async def test_uv_install_dev_dependency_in_project(mock_run: MagicMock):
    """Test UV install uses add subcommand when in UV project"""
    mock_run.return_value = MagicMock(returncode=0)
    mgr = UvPackageManager()

    result = await mgr._install(
        "package1 package2", upgrade=False, group="dev"
    )

    mock_run.assert_called_once_with(
        [
            "uv",
            "add",
            "--group",
            "dev",
            "--compile",
            "package1",
            "package2",
            "-p",
            PY_EXE,
        ],
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
        encoding="utf-8",
    )
    assert len(packages) == 2
    assert packages[0] == PackageDescription(name="package1", version="1.0.0")
    assert packages[1] == PackageDescription(name="package2", version="2.1.0")


@patch.object(UvPackageManager, "dependency_tree")
def test_uv_list_packages_with_tree_success(mock_dependency_tree: MagicMock):
    """Test UV list packages uses uv tree when available"""
    from marimo._server.models.packages import DependencyTreeNode

    # Mock dependency_tree to return a valid tree
    mock_tree = DependencyTreeNode(
        name="root",
        version="1.0.0",
        tags=[],
        dependencies=[
            DependencyTreeNode(
                name="z-package1",
                version="1.0.0",
                tags=[],
                dependencies=[
                    DependencyTreeNode(
                        name="package3",
                        version="3.0.0",
                        tags=[],
                        dependencies=[],
                    )
                ],
            ),
            DependencyTreeNode(
                name="package2",
                version=None,  # Test None version handling
                tags=[],
                dependencies=[
                    # Duplicate package
                    DependencyTreeNode(
                        name="package3",
                        version="3.0.0",
                        tags=[],
                        dependencies=[],
                    )
                ],
            ),
        ],
    )
    mock_dependency_tree.return_value = mock_tree

    mgr = UvPackageManager()
    packages = mgr.list_packages()

    # Should call dependency_tree first
    mock_dependency_tree.assert_called_once()

    # Should return packages from tree
    assert len(packages) == 3
    assert packages[0] == PackageDescription(name="package2", version="")
    assert packages[1] == PackageDescription(name="package3", version="3.0.0")
    assert packages[2] == PackageDescription(
        name="z-package1", version="1.0.0"
    )


@patch("subprocess.run")
@patch.object(UvPackageManager, "dependency_tree")
def test_uv_list_packages_tree_fallback_to_pip_list(
    mock_dependency_tree: MagicMock, mock_run: MagicMock
):
    """Test UV list packages falls back to pip list when tree is None"""
    # Mock dependency_tree to return None (fallback case)
    mock_dependency_tree.return_value = None

    # Mock subprocess for pip list
    mock_output = json.dumps(
        [
            {"name": "fallback1", "version": "1.5.0"},
            {"name": "fallback2", "version": "2.3.0"},
        ]
    )
    mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

    mgr = UvPackageManager()
    packages = mgr.list_packages()

    # Should try dependency_tree first
    mock_dependency_tree.assert_called_once()

    # Should fall back to subprocess call
    mock_run.assert_called_once_with(
        ["uv", "pip", "list", "--format=json", "-p", PY_EXE],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    # Should return packages from fallback method
    assert len(packages) == 2
    assert packages[0] == PackageDescription(name="fallback1", version="1.5.0")
    assert packages[1] == PackageDescription(name="fallback2", version="2.3.0")


@patch.object(UvPackageManager, "dependency_tree")
def test_uv_list_packages_with_empty_tree(mock_dependency_tree: MagicMock):
    """Test UV list packages handles empty dependency tree"""
    from marimo._server.models.packages import DependencyTreeNode

    # Mock dependency_tree to return tree with no dependencies
    mock_tree = DependencyTreeNode(
        name="root", version="1.0.0", tags=[], dependencies=[]
    )
    mock_dependency_tree.return_value = mock_tree

    mgr = UvPackageManager()
    packages = mgr.list_packages()

    # Should call dependency_tree
    mock_dependency_tree.assert_called_once()

    # Should return empty list
    assert len(packages) == 0
    assert packages == []


@patch.dict(
    "os.environ",
    {
        "VIRTUAL_ENV": "/path/to/venv",
        "UV_PROJECT_ENVIRONMENT": "/path/to/venv",
    },
    clear=True,
)
def test_uv_is_in_uv_project_uv_project_environment_match():
    """Test is_in_uv_project returns True when UV_PROJECT_ENVIRONMENT equals VIRTUAL_ENV"""
    mgr = UvPackageManager()
    assert mgr.is_in_uv_project is True


@patch.dict(
    "os.environ",
    {
        "VIRTUAL_ENV": "/path/to/venv",
        "UV_PROJECT_ENVIRONMENT": "/different/path",
    },
    clear=True,
)
def test_uv_is_in_uv_project_uv_project_environment_mismatch():
    """Test is_in_uv_project returns False when UV_PROJECT_ENVIRONMENT doesn't match VIRTUAL_ENV"""
    mgr = UvPackageManager()
    assert mgr.is_in_uv_project is False


# Encoding tests for Windows compatibility


@patch("subprocess.run")
def test_pip_list_packages_uses_utf8_encoding(mock_run: MagicMock):
    """Test that pip list uses UTF-8 encoding to handle non-ASCII characters"""
    mock_output = json.dumps(
        [
            {"name": "package-中文", "version": "1.0.0"},
            {"name": "пакет", "version": "2.0.0"},
        ]
    )
    mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
    mgr = PipPackageManager()

    with patch.object(mgr, "is_manager_installed", return_value=True):
        packages = mgr.list_packages()

    # Verify encoding='utf-8' is passed
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args[1]
    assert call_kwargs.get("encoding") == "utf-8"
    assert call_kwargs.get("text") is True


@patch("subprocess.run")
def test_uv_dependency_tree_uses_utf8_encoding(mock_run: MagicMock):
    """Test that uv tree uses UTF-8 encoding"""
    mock_output = "test-package v1.0.0\n"
    mock_run.return_value = MagicMock(
        returncode=0, stdout=mock_output, stderr=""
    )
    mgr = UvPackageManager()

    mgr.dependency_tree(filename="test.py")

    # Verify encoding='utf-8' is passed
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args[1]
    assert call_kwargs.get("encoding") == "utf-8"
    assert call_kwargs.get("text") is True


@patch("subprocess.run")
def test_uv_pip_list_uses_utf8_encoding(mock_run: MagicMock):
    """Test that uv pip list uses UTF-8 encoding"""
    mock_output = json.dumps([{"name": "test-pkg", "version": "1.0.0"}])
    mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
    mgr = UvPackageManager()

    # Mock dependency_tree to return None so it falls back to pip list
    with patch.object(mgr, "dependency_tree", return_value=None):
        mgr.list_packages()

    # Verify encoding='utf-8' is passed
    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args[1]
    assert call_kwargs.get("encoding") == "utf-8"
    assert call_kwargs.get("text") is True


def test_has_script_metadata_with_metadata(tmp_path: Path):
    """Test that _has_script_metadata returns True when script has metadata"""
    script_file = tmp_path / "script_with_metadata.py"
    script_file.write_text(
        """# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests",
#   "pandas",
# ]
# ///

import marimo as mo
"""
    )

    mgr = UvPackageManager()
    assert mgr._has_script_metadata(str(script_file)) is True


def test_has_script_metadata_without_metadata(tmp_path: Path):
    """Test that _has_script_metadata returns False when script has no metadata"""
    script_file = tmp_path / "script_without_metadata.py"
    script_file.write_text(
        """import marimo as mo
import pandas as pd

# This is a regular comment
# Not a script metadata block
"""
    )

    mgr = UvPackageManager()
    assert mgr._has_script_metadata(str(script_file)) is False


def test_has_script_metadata_nonexistent_file():
    """Test that _has_script_metadata returns False for nonexistent files"""
    mgr = UvPackageManager()
    assert mgr._has_script_metadata("/nonexistent/path/to/file.py") is False


def test_has_script_metadata_binary_file(tmp_path: Path):
    """Test that _has_script_metadata returns False for binary files"""
    binary_file = tmp_path / "binary.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

    mgr = UvPackageManager()
    assert mgr._has_script_metadata(str(binary_file)) is False


@patch("subprocess.Popen")
@patch("subprocess.run")
@patch.object(UvPackageManager, "is_in_uv_project", False)
async def test_uv_install_cache_error_fallback(
    mock_run: MagicMock, mock_popen: MagicMock
):
    """Test UV install retries with --no-cache on cache write errors"""
    # Mock the first install attempt (via Popen) to fail with cache error
    mock_process = MagicMock()
    mock_process.wait.return_value = 1  # Failure
    mock_process.stdout.readline.side_effect = [
        b"  \xc3\x97 Failed to download and build `pyqtree==1.0.0`\n",
        b"  \xe2\x94\x9c\xe2\x94\x80\xe2\x96\xb6 Failed to write to the distribution cache\n",
        b"  \xe2\x95\xb0\xe2\x94\x80\xe2\x96\xb6 Operation not permitted (os error 1)\n",
        b"",  # End of output
    ]
    mock_popen.return_value = mock_process

    # Mock the retry (via run) to succeed
    mock_run.return_value = MagicMock(returncode=0)

    mgr = UvPackageManager()
    with patch.object(mgr, "is_manager_installed", return_value=True):
        result = await mgr._install("datamapplot", upgrade=False, group=None)

    # First attempt should use Popen
    mock_popen.assert_called_once_with(
        [
            "uv",
            "pip",
            "install",
            "--compile",
            "datamapplot",
            "-p",
            PY_EXE,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=False,
        bufsize=0,
    )

    # Retry should add --no-cache flag
    mock_run.assert_called_once_with(
        [
            "uv",
            "pip",
            "install",
            "--compile",
            "datamapplot",
            "-p",
            PY_EXE,
            "--no-cache",
        ],
    )

    # Should ultimately succeed
    assert result is True


@patch("subprocess.Popen")
@patch.object(UvPackageManager, "is_in_uv_project", False)
async def test_uv_install_no_fallback_on_different_error(
    mock_popen: MagicMock,
):
    """Test UV install does not retry when error is not cache-related"""
    # Mock the install attempt to fail with a different error
    mock_process = MagicMock()
    mock_process.wait.return_value = 1  # Failure
    mock_process.stdout.readline.side_effect = [
        b"  \xc3\x97 Failed to download package\n",
        b"  \xe2\x94\x9c\xe2\x94\x80\xe2\x96\xb6 Network error\n",
        b"",  # End of output
    ]
    mock_popen.return_value = mock_process

    mgr = UvPackageManager()
    with patch.object(mgr, "is_manager_installed", return_value=True):
        result = await mgr._install(
            "nonexistent-package", upgrade=False, group=None
        )

    # Should only call Popen once (no retry)
    mock_popen.assert_called_once()

    # Should fail
    assert result is False


@patch("subprocess.run")
@patch.object(UvPackageManager, "is_in_uv_project", True)
async def test_uv_install_in_project_no_fallback(mock_run: MagicMock):
    """Test UV install in a project does not use fallback mechanism"""
    mock_run.return_value = MagicMock(returncode=1)  # Failure
    mgr = UvPackageManager()

    result = await mgr._install("package1", upgrade=False, group=None)

    # Should only call run once (no fallback for project mode)
    mock_run.assert_called_once_with(
        ["uv", "add", "--compile", "package1", "-p", PY_EXE],
    )

    # Should fail without retry
    assert result is False
