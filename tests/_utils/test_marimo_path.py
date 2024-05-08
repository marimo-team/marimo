from __future__ import annotations

import os
from pathlib import Path

import pytest

from marimo._utils.marimo_path import MarimoPath


def test_init():
    # Test with a valid Python file
    path = Path(__file__)
    mp = MarimoPath(path)
    assert mp.path == path

    # Test with a valid Markdown file
    path = Path("README.md")
    mp = MarimoPath(path)
    assert mp.path == path

    # Test with an invalid file
    path = Path("invalid.txt")
    with pytest.raises(ValueError):
        MarimoPath(path)


def test_is_valid_path():
    # Test with a valid Python file
    assert MarimoPath.is_valid_path(__file__)

    # Test with a valid Markdown file
    assert MarimoPath.is_valid_path("README.md")

    # Test with an invalid file
    assert not MarimoPath.is_valid_path("invalid.txt")


def test_is_valid():
    # Test with a Python file
    mp = MarimoPath(__file__)
    assert mp.is_valid()
    assert mp.is_python()
    assert not mp.is_markdown()

    # Test with a Markdown file
    mp = MarimoPath("README.md")
    assert mp.is_valid()
    assert not mp.is_python()
    assert mp.is_markdown()


def test_rename(tmp_path: Path):
    # Create a temporary file
    tmp_file = tmp_path / "test.py"
    tmp_file.write_text("test")

    # Rename the file
    new_file = tmp_path / "new_test.py"
    mp = MarimoPath(tmp_file)
    mp.rename(new_file)
    assert not tmp_file.exists()
    assert new_file.exists()

    # Try to rename to an existing file
    with pytest.raises(ValueError):
        mp.rename(new_file)


def test_write_text(tmp_path: Path):
    # Create a temporary file
    tmp_file = tmp_path / "test.py"
    mp = MarimoPath(tmp_file)

    # Write some text to the file
    text = "Hello, world!"
    mp.write_text(text)
    assert tmp_file.read_text() == text


def test_properties():
    mp = MarimoPath(__file__)

    # Test short_name
    assert mp.short_name == os.path.basename(__file__)

    # Test relative_name
    assert mp.relative_name == os.path.relpath(__file__)

    # Test absolute_name
    assert mp.absolute_name == os.path.abspath(__file__)

    # Test last_modified
    assert mp.last_modified == os.path.getmtime(__file__)
