from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from marimo._cli.venv import get_configured_venv_python


def test_get_configured_venv_python_returns_none_when_not_configured() -> None:
    """Test returns None when venv not in config."""
    config: dict[str, Any] = {}  # No venv configured
    result = get_configured_venv_python(config)
    assert result is None


def test_get_configured_venv_python_returns_none_when_venv_empty() -> None:
    """Test returns None when venv is empty string."""
    config: dict[str, Any] = {"venv": ""}
    result = get_configured_venv_python(config)
    assert result is None


def test_get_configured_venv_python_returns_path_when_valid(
    tmp_path: Path,
) -> None:
    """Test returns Python path when venv is valid."""
    # Create a mock venv with Python
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    if sys.platform == "win32":
        bin_dir = venv_dir / "Scripts"
        python_name = "python.exe"
    else:
        bin_dir = venv_dir / "bin"
        python_name = "python"
    bin_dir.mkdir()
    python_path = bin_dir / python_name
    python_path.touch()

    config: dict[str, Any] = {"venv": str(venv_dir)}
    result = get_configured_venv_python(config)
    assert result is not None
    assert result.endswith(python_name)


def test_get_configured_venv_python_raises_on_missing_venv() -> None:
    """Test raises ValueError when configured venv doesn't exist."""
    config: dict[str, Any] = {"venv": "/nonexistent/venv/path"}
    with pytest.raises(ValueError, match="does not exist"):
        get_configured_venv_python(config)


def test_get_configured_venv_python_raises_on_no_python(
    tmp_path: Path,
) -> None:
    """Test raises ValueError when venv has no Python interpreter."""
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()  # Empty venv, no bin/python

    config: dict[str, Any] = {"venv": str(venv_dir)}
    with pytest.raises(ValueError, match="No Python interpreter"):
        get_configured_venv_python(config)


def test_get_configured_venv_python_resolves_relative_path(
    tmp_path: Path,
) -> None:
    """Test that relative venv paths are resolved from base_path."""
    # Create a mock venv with Python
    venv_dir = tmp_path / "venvs" / "myenv"
    venv_dir.mkdir(parents=True)
    if sys.platform == "win32":
        bin_dir = venv_dir / "Scripts"
        python_name = "python.exe"
    else:
        bin_dir = venv_dir / "bin"
        python_name = "python"
    bin_dir.mkdir()
    python_path = bin_dir / python_name
    python_path.touch()

    # Create a script file in tmp_path
    script_path = tmp_path / "notebook.py"
    script_path.touch()

    # Relative path from script location
    config: dict[str, Any] = {"venv": "venvs/myenv"}
    result = get_configured_venv_python(config, base_path=str(script_path))
    assert result is not None
    assert result.endswith(python_name)
