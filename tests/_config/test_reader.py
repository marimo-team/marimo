from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from marimo._config.reader import (
    find_nearest_pyproject_toml,
    read_marimo_config,
    read_pyproject_marimo_config,
)
from marimo._utils.toml import read_toml


def test_read_toml():
    toml_content = b"""
    [section]
    key = "value"
    """
    with patch("builtins.open", mock_open(read_data=toml_content)):
        result = read_toml("dummy.toml")
        assert result == {"section": {"key": "value"}}


def test_read_marimo_config():
    config_content = b"""
    [formatting]
    line_length = 79

    [save]
    autosave_delay = 1000
    format_on_save = true
    autosave = "after_delay"

    [novalidate]
    old_keys_are_ok = true
    """
    with patch("builtins.open", mock_open(read_data=config_content)):
        result = read_marimo_config("marimo.toml")
        assert result == {
            "formatting": {"line_length": 79},
            "save": {
                "autosave_delay": 1000,
                "format_on_save": True,
                "autosave": "after_delay",
            },
            "novalidate": {"old_keys_are_ok": True},
        }


def test_read_pyproject_config_with_marimo_section(tmp_path: Path):
    pyproject_content = """
    [tool.marimo]
    formatting = {line_length = 79}

    [tool.marimo.save]
    autosave_delay = 1000
    format_on_save = true
    autosave = "after_delay"

    [tool.marimo.novalidate]
    old_keys_are_ok = true
    """
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(pyproject_content)
    nearest_pyproject_toml = find_nearest_pyproject_toml(tmp_path)
    assert nearest_pyproject_toml is not None
    result = read_pyproject_marimo_config(nearest_pyproject_toml)
    assert result == {
        "formatting": {"line_length": 79},
        "save": {
            "autosave_delay": 1000,
            "format_on_save": True,
            "autosave": "after_delay",
        },
        "novalidate": {"old_keys_are_ok": True},
    }


def test_read_pyproject_config_without_marimo_section(tmp_path: Path):
    pyproject_content = """
    [tool.idk]
    name = "foo"
    """
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(pyproject_content)
    nearest_pyproject_toml = find_nearest_pyproject_toml(tmp_path)
    assert nearest_pyproject_toml is not None
    result = read_pyproject_marimo_config(nearest_pyproject_toml)
    assert result is None


def test_read_pyproject_config_invalid_marimo_section(tmp_path: Path):
    pyproject_content = """
    [tool]
    marimo = "invalid"
    """
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(pyproject_content)
    nearest_pyproject_toml = find_nearest_pyproject_toml(tmp_path)
    assert nearest_pyproject_toml is not None
    result = read_pyproject_marimo_config(nearest_pyproject_toml)
    assert result is None


def test_read_pyproject_config_no_file(tmp_path: Path):
    nearest_pyproject_toml = find_nearest_pyproject_toml(tmp_path)
    assert nearest_pyproject_toml is None


def testfind_nearest_pyproject_toml():
    with tempfile.TemporaryDirectory() as temp_dir:
        parent_dir = os.path.join(temp_dir, "parent")
        os.makedirs(parent_dir)
        pyproject_path = os.path.join(parent_dir, "pyproject.toml")
        with open(pyproject_path, "w") as f:
            f.write("")

        start_path = os.path.join(parent_dir, "child")
        os.makedirs(start_path)
        result = find_nearest_pyproject_toml(start_path)
        assert result == Path(pyproject_path)


def testfind_nearest_pyproject_toml_not_found():
    with tempfile.TemporaryDirectory() as temp_dir:
        result = find_nearest_pyproject_toml(temp_dir)
        assert result is None


def test_read_toml_invalid_content():
    invalid_toml = b"""
    [invalid
    key = value
    """
    import tomllib

    with patch("builtins.open", mock_open(read_data=invalid_toml)):
        with pytest.raises(tomllib.TOMLDecodeError):
            read_toml("dummy.toml")
