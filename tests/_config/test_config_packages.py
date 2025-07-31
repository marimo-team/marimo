from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from marimo._config.packages import (
    infer_package_manager,
    infer_package_manager_from_lockfile,
    infer_package_manager_from_pyproject,
)


@pytest.fixture
def mock_cwd(tmp_path: Path):
    """Creates a temporary directory and sets it as CWD"""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)


def test_infer_package_manager_from_pyproject():
    # Test poetry detection
    with patch(
        "marimo._config.packages.read_toml",
        return_value={"tool": {"poetry": {}}},
    ):
        assert (
            infer_package_manager_from_pyproject(Path("pyproject.toml"))
            == "poetry"
        )

    # Test no tool section
    with patch("marimo._config.packages.read_toml", return_value={}):
        assert (
            infer_package_manager_from_pyproject(Path("pyproject.toml"))
            is None
        )

    # Test exception handling
    with patch("marimo._config.packages.read_toml", side_effect=Exception):
        assert (
            infer_package_manager_from_pyproject(Path("pyproject.toml"))
            is None
        )


def test_infer_package_manager_from_lockfile(mock_cwd: Path):
    # Test poetry.lock
    (mock_cwd / "poetry.lock").touch()
    assert infer_package_manager_from_lockfile(mock_cwd) == "poetry"
    (mock_cwd / "poetry.lock").unlink()

    # Test pixi.lock
    (mock_cwd / "pixi.lock").touch()
    assert infer_package_manager_from_lockfile(mock_cwd) == "pixi"
    (mock_cwd / "pixi.lock").unlink()

    # Test no lockfile
    for f in mock_cwd.iterdir():
        f.unlink()
    assert infer_package_manager_from_lockfile(mock_cwd) is None


TEST_CASES: list[
    tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]
] = [
    # Test pyproject.toml with poetry
    ({"pyproject.toml": {"tool": {"poetry": {}}}}, {}, {}, "poetry"),
    # Test lockfile detection
    ({"poetry.lock": ""}, {}, {}, "poetry"),
    # Test pixi.toml
    ({"pixi.toml": ""}, {}, {}, "pixi"),
    # Test fallback to pip
    ({}, {}, {}, "pip"),
    # Test fallback to uv when running inside `uv run` / `uvx`
    ({}, {"UV": "/usr/bin/uv"}, {}, "uv"),
]

if sys.platform != "win32":
    TEST_CASES.extend(
        [
            # Test uv virtualenv
            ({}, {"VIRTUAL_ENV": "/path/uv/env"}, {}, "uv"),
            # Test regular virtualenv
            ({}, {}, {"base_prefix": "/usr", "prefix": "/venv"}, "pip"),
        ]
    )


@pytest.mark.parametrize(
    ("files", "env_vars", "sys_attrs", "expected"),
    TEST_CASES,
)
def test_infer_package_manager(
    mock_cwd: Path,
    files: dict[str, Any],
    env_vars: dict[str, Any],
    sys_attrs: dict[str, Any],
    expected: str,
):
    # Write a default pyproject.toml file
    (mock_cwd / "pyproject.toml").write_text(
        """
        [project]
        name = "test"
        """
    )

    # Create test files
    for filename, content in files.items():
        if isinstance(content, dict):
            import tomlkit

            with open(mock_cwd / filename, "w") as f:
                tomlkit.dump(content, f)
        else:
            (mock_cwd / filename).write_text(content)

    # Mock environment variables
    with patch.dict(os.environ, env_vars):
        # Mock sys attributes
        if sys_attrs:
            with patch.multiple(sys, **sys_attrs):
                assert infer_package_manager() == expected
        else:
            assert infer_package_manager() == expected
