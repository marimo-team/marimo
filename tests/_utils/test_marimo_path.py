from __future__ import annotations

import os
from pathlib import Path

import pytest

from marimo._utils.marimo_path import MarimoPath
from tests.mocks import EDGE_CASE_FILENAMES


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


@pytest.mark.parametrize(
    "filename",
    [
        *EDGE_CASE_FILENAMES,
        "café.qmd",
        "🚀 my notebook.md",
    ],
)
def test_marimo_path_with_edge_case_filenames(tmp_path: Path, filename: str):
    """Test MarimoPath with unicode, spaces, and special characters."""
    file_path = tmp_path / filename
    file_path.write_text("# test content", encoding="utf-8")

    # Should be able to create MarimoPath
    mp = MarimoPath(file_path)
    assert mp.path == file_path
    assert mp.is_valid()

    # Should handle file operations correctly
    content = mp.read_text()
    assert content == "# test content"

    # Should handle properties correctly
    assert mp.short_name == filename
    assert filename in mp.absolute_name

    # Should handle rename correctly
    new_filename = f"new_{filename}"
    new_path = tmp_path / new_filename
    mp.rename(new_path)
    assert not file_path.exists()
    assert new_path.exists()


@pytest.mark.parametrize(
    "filename",
    [
        # Valid files
        "café.md",
        "测试.qmd",
        "café notebook.markdown",
        *EDGE_CASE_FILENAMES,
    ],
)
def test_is_valid_path_with_edge_case_filenames(filename: str):
    """Test MarimoPath.is_valid_path with unicode and spaces."""
    assert MarimoPath.is_valid_path(filename)


@pytest.mark.parametrize(
    "filename",
    [
        "tést.txt",
        "café.doc",
        "测试.xyz",
        "test file.pdf",
        "test.py.txt",
    ],
)
def test_is_valid_path_with_invalid_filenames(filename: str):
    assert not MarimoPath.is_valid_path(filename)
