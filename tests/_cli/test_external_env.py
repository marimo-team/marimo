# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._cli.external_env import (
    find_active_python,
    find_conda_python,
    find_python_in_venv,
    resolve_python_path,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestResolvePythonPath:
    def test_empty_config(self) -> None:
        """Empty config returns None."""
        assert resolve_python_path({}) is None

    def test_python_path_exists(self, tmp_path: Path) -> None:
        """Direct python path that exists is returned."""
        # Create a fake python executable
        if sys.platform == "win32":
            python = tmp_path / "python.exe"
        else:
            python = tmp_path / "python"
        python.touch()
        python.chmod(0o755)

        result = resolve_python_path({"python": str(python)})
        assert result == str(python.resolve())

    def test_python_path_not_exists(self) -> None:
        """Non-existent python path returns None."""
        result = resolve_python_path({"python": "/nonexistent/python"})
        assert result is None

    def test_use_active_with_virtual_env(self, tmp_path: Path) -> None:
        """use_active finds Python from VIRTUAL_ENV."""
        venv_path = tmp_path / "venv"
        if sys.platform == "win32":
            bin_dir = venv_path / "Scripts"
            python = bin_dir / "python.exe"
        else:
            bin_dir = venv_path / "bin"
            python = bin_dir / "python"
        bin_dir.mkdir(parents=True)
        python.touch()
        python.chmod(0o755)

        with patch.dict(
            os.environ, {"VIRTUAL_ENV": str(venv_path)}, clear=False
        ):
            result = resolve_python_path({"use_active": True})
            assert result == str(python.resolve())

    def test_use_active_with_conda_prefix(self, tmp_path: Path) -> None:
        """use_active finds Python from CONDA_PREFIX."""
        conda_path = tmp_path / "conda_env"
        if sys.platform == "win32":
            bin_dir = conda_path / "Scripts"
            python = bin_dir / "python.exe"
        else:
            bin_dir = conda_path / "bin"
            python = bin_dir / "python"
        bin_dir.mkdir(parents=True)
        python.touch()
        python.chmod(0o755)

        # Clear VIRTUAL_ENV to test CONDA_PREFIX fallback
        env = {"CONDA_PREFIX": str(conda_path)}
        if "VIRTUAL_ENV" in os.environ:
            env["VIRTUAL_ENV"] = ""

        with patch.dict(os.environ, env, clear=False):
            result = resolve_python_path({"use_active": True})
            assert result == str(python.resolve())

    def test_use_active_no_env_set(self) -> None:
        """use_active returns None when no env is active."""
        with patch.dict(
            os.environ, {"VIRTUAL_ENV": "", "CONDA_PREFIX": ""}, clear=False
        ):
            result = resolve_python_path({"use_active": True})
            assert result is None


class TestFindPythonInVenv:
    def test_venv_with_python(self, tmp_path: Path) -> None:
        """Finds Python in a valid venv."""
        if sys.platform == "win32":
            bin_dir = tmp_path / "Scripts"
            python = bin_dir / "python.exe"
        else:
            bin_dir = tmp_path / "bin"
            python = bin_dir / "python"
        bin_dir.mkdir()
        python.touch()
        python.chmod(0o755)

        result = find_python_in_venv(str(tmp_path))
        assert result == str(python.resolve())

    def test_venv_no_python(self, tmp_path: Path) -> None:
        """Returns None if Python not found in venv."""
        result = find_python_in_venv(str(tmp_path))
        assert result is None

    def test_venv_not_exists(self) -> None:
        """Returns None if venv doesn't exist."""
        result = find_python_in_venv("/nonexistent/venv")
        assert result is None


class TestFindActiveEnv:
    def test_virtual_env_set(self, tmp_path: Path) -> None:
        """Finds Python from VIRTUAL_ENV."""
        if sys.platform == "win32":
            bin_dir = tmp_path / "Scripts"
            python = bin_dir / "python.exe"
        else:
            bin_dir = tmp_path / "bin"
            python = bin_dir / "python"
        bin_dir.mkdir()
        python.touch()
        python.chmod(0o755)

        with patch.dict(
            os.environ, {"VIRTUAL_ENV": str(tmp_path)}, clear=False
        ):
            result = find_active_python()
            assert result == str(python.resolve())

    def test_conda_prefix_fallback(self, tmp_path: Path) -> None:
        """Falls back to CONDA_PREFIX if VIRTUAL_ENV not set."""
        if sys.platform == "win32":
            bin_dir = tmp_path / "Scripts"
            python = bin_dir / "python.exe"
        else:
            bin_dir = tmp_path / "bin"
            python = bin_dir / "python"
        bin_dir.mkdir()
        python.touch()
        python.chmod(0o755)

        env = {"CONDA_PREFIX": str(tmp_path)}
        if "VIRTUAL_ENV" in os.environ:
            env["VIRTUAL_ENV"] = ""

        with patch.dict(os.environ, env, clear=False):
            result = find_active_python()
            assert result == str(python.resolve())

    def test_no_env_set(self) -> None:
        """Returns None if no env is active."""
        with patch.dict(
            os.environ, {"VIRTUAL_ENV": "", "CONDA_PREFIX": ""}, clear=False
        ):
            result = find_active_python()
            assert result is None


class TestFindCondaPython:
    def test_conda_not_installed(self) -> None:
        """Returns None if conda CLI not found."""
        with patch("shutil.which", return_value=None):
            result = find_conda_python("myenv")
            assert result is None

    @pytest.mark.skipif(
        os.environ.get("CONDA_PREFIX") is None, reason="Conda not available"
    )
    def test_conda_env_exists(self) -> None:
        """If conda is available, test with base environment."""
        # This test only runs if conda is available
        result = find_conda_python("base")
        # May or may not find base env depending on system config
        # Just ensure it doesn't crash
        assert (
            result is None
            or result.endswith("python")
            or result.endswith("python.exe")
        )


class TestPyProjectEnvConfig:
    def test_env_config_parsing(self, tmp_path: Path) -> None:
        """Test that env_config is correctly parsed from PEP 723 metadata."""
        from marimo._utils.inline_script_metadata import PyProjectReader

        notebook = tmp_path / "test.py"
        notebook.write_text("""# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas"]
#
# [tool.marimo.env]
# use_active = true
# ///

import marimo as mo
""")

        reader = PyProjectReader.from_filename(str(notebook))
        assert reader.env_config == {"use_active": True}

    def test_env_config_with_python_path(self, tmp_path: Path) -> None:
        """Test env_config with explicit python path."""
        from marimo._utils.inline_script_metadata import PyProjectReader

        notebook = tmp_path / "test.py"
        notebook.write_text("""# /// script
# [tool.marimo.env]
# python = "/usr/bin/python3"
# ///

import marimo as mo
""")

        reader = PyProjectReader.from_filename(str(notebook))
        assert reader.env_config == {"python": "/usr/bin/python3"}

    def test_env_config_empty(self, tmp_path: Path) -> None:
        """Test that empty env_config returns empty dict."""
        from marimo._utils.inline_script_metadata import PyProjectReader

        notebook = tmp_path / "test.py"
        notebook.write_text("""# /// script
# dependencies = ["pandas"]
# ///

import marimo as mo
""")

        reader = PyProjectReader.from_filename(str(notebook))
        assert reader.env_config == {}


class TestSandboxConflict:
    def test_conflict_raises_error(self, tmp_path: Path) -> None:
        """Test that sandbox + env config raises error."""
        from click import UsageError

        from marimo._cli.sandbox import check_external_env_sandbox_conflict

        notebook = tmp_path / "test.py"
        notebook.write_text("""# /// script
# [tool.marimo.env]
# use_active = true
# ///

import marimo as mo
""")

        # Create a venv so use_active resolves
        if sys.platform == "win32":
            bin_dir = tmp_path / "venv" / "Scripts"
            python = bin_dir / "python.exe"
        else:
            bin_dir = tmp_path / "venv" / "bin"
            python = bin_dir / "python"
        bin_dir.mkdir(parents=True)
        python.touch()
        python.chmod(0o755)

        with patch.dict(
            os.environ, {"VIRTUAL_ENV": str(tmp_path / "venv")}, clear=False
        ):
            with pytest.raises(UsageError, match="Cannot use --sandbox"):
                check_external_env_sandbox_conflict(
                    name=str(notebook), sandbox=True
                )

    def test_no_conflict_without_sandbox(self, tmp_path: Path) -> None:
        """Test no error when sandbox is False/None."""
        from marimo._cli.sandbox import check_external_env_sandbox_conflict

        notebook = tmp_path / "test.py"
        notebook.write_text("""# /// script
# [tool.marimo.env]
# use_active = true
# ///

import marimo as mo
""")

        # Should not raise
        check_external_env_sandbox_conflict(name=str(notebook), sandbox=False)
        check_external_env_sandbox_conflict(name=str(notebook), sandbox=None)
