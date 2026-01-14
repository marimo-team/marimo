from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from marimo._session._venv import (
    get_configured_venv_python,
    get_kernel_pythonpath,
)


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


def test_get_kernel_pythonpath_includes_marimo_dir() -> None:
    """Test that kernel PYTHONPATH includes marimo's parent directory."""
    import marimo

    pythonpath = get_kernel_pythonpath()
    paths = pythonpath.split(os.pathsep)

    marimo_dir = os.path.dirname(os.path.dirname(marimo.__file__))
    assert marimo_dir in paths, f"marimo dir {marimo_dir} not in {paths}"


def test_get_kernel_pythonpath_detects_module_via_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that module detection works by importing and checking __file__."""
    from types import ModuleType

    fake_zmq = ModuleType("zmq")
    fake_zmq.__file__ = "/fake/site-packages/zmq/__init__.py"
    monkeypatch.setitem(sys.modules, "zmq", fake_zmq)

    pythonpath = get_kernel_pythonpath()
    paths = pythonpath.split(os.pathsep)

    assert "/fake/site-packages" in paths


def test_get_kernel_pythonpath_skips_module_without_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that modules without __file__ are skipped gracefully."""
    from types import ModuleType

    fake_zmq = ModuleType("zmq")
    # Don't set __file__ - simulates built-in or namespace package
    monkeypatch.setitem(sys.modules, "zmq", fake_zmq)

    pythonpath = get_kernel_pythonpath()
    assert pythonpath  # Should still have marimo dir at minimum


def test_get_kernel_pythonpath_handles_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that ImportError is handled gracefully."""
    import marimo

    monkeypatch.delitem(sys.modules, "zmq", raising=False)
    monkeypatch.delitem(sys.modules, "msgspec", raising=False)

    original_import = __builtins__["__import__"]  # type: ignore[index]

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in ("zmq", "msgspec"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    pythonpath = get_kernel_pythonpath()
    paths = pythonpath.split(os.pathsep)

    marimo_dir = os.path.dirname(os.path.dirname(marimo.__file__))
    assert marimo_dir in paths


def test_get_kernel_pythonpath_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that duplicate paths are deduplicated."""
    from types import ModuleType

    fake_zmq = ModuleType("zmq")
    fake_zmq.__file__ = "/shared/site-packages/zmq/__init__.py"
    fake_msgspec = ModuleType("msgspec")
    fake_msgspec.__file__ = "/shared/site-packages/msgspec/__init__.py"

    monkeypatch.setitem(sys.modules, "zmq", fake_zmq)
    monkeypatch.setitem(sys.modules, "msgspec", fake_msgspec)

    pythonpath = get_kernel_pythonpath()
    paths = pythonpath.split(os.pathsep)

    assert paths.count("/shared/site-packages") == 1
