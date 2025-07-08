from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import pytest

from marimo._plugins.ui._impl.file_browser import (
    FileBrowserFileInfo,
    ListDirectoryArgs,
    ListDirectoryResponse,
    file_browser,
)


def test_file_browser_init() -> None:
    # Use a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        fb = file_browser(initial_path=temp_dir)
        assert isinstance(fb._initial_path, Path)
        assert str(fb._initial_path) == str(Path(temp_dir).resolve())
        assert fb._selection_mode == "file"
        assert fb._filetypes == set()
        assert fb._restrict_navigation is False

        # Test with custom filetypes
        custom_filetypes = [".txt", ".csv"]
        fb = file_browser(
            initial_path=temp_dir,
            filetypes=custom_filetypes,
            selection_mode="directory",
            restrict_navigation=True,
        )
        assert fb._initial_path == Path(temp_dir).resolve()
        assert fb._filetypes == set(custom_filetypes)
        assert fb._selection_mode == "directory"
        assert fb._restrict_navigation is True


def test_list_directory() -> None:
    fb = file_browser(
        initial_path=Path.cwd(), filetypes=[".txt"], selection_mode="file"
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(Path.cwd())))
    assert isinstance(response, ListDirectoryResponse)
    for file_info in response.files:
        assert file_info["is_directory"] or file_info["path"].endswith(
            tuple(fb._filetypes)
        )


def test_navigation_restriction() -> None:
    fb = file_browser(initial_path=Path.cwd(), restrict_navigation=True)
    with pytest.raises(RuntimeError) as e:
        fb._list_directory(ListDirectoryArgs(path=str(Path.cwd().parent)))
    assert "Navigation is restricted" in str(e.value)


def test_name_method() -> None:
    fb = file_browser(initial_path=Path.cwd())
    fb._value = [
        FileBrowserFileInfo(
            id="1",
            path=Path("/some/path/file.txt"),
            name="file.txt",
            is_directory=False,
        )
    ]
    assert fb.name(0) == "file.txt"
    assert fb.name(1) is None


def test_path_method() -> None:
    fb = file_browser(initial_path=Path.cwd())
    fb._value = [
        FileBrowserFileInfo(
            id="1",
            path=Path("/some/path/file.txt"),
            name="file.txt",
            is_directory=False,
        )
    ]
    assert fb.path(0) == Path("/some/path/file.txt")
    assert fb.path(1) is None


def test_natural_sorting(tmp_path: Path) -> None:
    """Test that files are sorted using natural sort order."""
    # Create test files with names that should be naturally sorted
    test_files = [
        "file10.txt",
        "file2.txt",
        "file1.txt",
        "file20.txt",
        "fileB.txt",
        "fileA.txt",
        "file100.txt",
    ]

    for filename in test_files:
        (tmp_path / filename).touch()

    fb = file_browser(initial_path=tmp_path)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # Extract file names from response
    file_names = [f["name"] for f in response.files if not f["is_directory"]]

    # Expected natural sort order
    expected_order = [
        "file1.txt",
        "file2.txt",
        "file10.txt",
        "file20.txt",
        "file100.txt",
        "fileA.txt",
        "fileB.txt",
    ]

    assert file_names == expected_order


def test_directories_sorted_before_files(tmp_path: Path) -> None:
    """Test that directories are sorted before files."""
    # Create test directories and files
    (tmp_path / "z_directory").mkdir()
    (tmp_path / "a_directory").mkdir()
    (tmp_path / "a_file.txt").touch()
    (tmp_path / "z_file.txt").touch()

    fb = file_browser(initial_path=tmp_path)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # Extract names and types
    items = [(f["name"], f["is_directory"]) for f in response.files]

    # Check that all directories come before all files
    directory_names = [name for name, is_dir in items if is_dir]
    file_names = [name for name, is_dir in items if not is_dir]

    # Directories should be sorted naturally among themselves
    assert directory_names == ["a_directory", "z_directory"]
    # Files should be sorted naturally among themselves
    assert file_names == ["a_file.txt", "z_file.txt"]

    # All directory names should come before all file names in the full list
    all_names = [name for name, _ in items]
    directory_end_index = len(directory_names)
    assert all_names[:directory_end_index] == directory_names
    assert all_names[directory_end_index:] == file_names


def test_mixed_alphanumeric_sorting(tmp_path: Path) -> None:
    """Test natural sorting with mixed alphanumeric patterns."""
    test_items = [
        ("dir100", True),  # directory
        ("dir2", True),  # directory
        ("dir10", True),  # directory
        ("file100.txt", False),  # file
        ("file2.txt", False),  # file
        ("file10.txt", False),  # file
    ]

    # Create test directories and files
    for name, is_dir in test_items:
        if is_dir:
            (tmp_path / name).mkdir()
        else:
            (tmp_path / name).touch()

    fb = file_browser(initial_path=tmp_path)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # Extract names preserving order from response
    result_names = [f["name"] for f in response.files]

    # Expected order: directories first (naturally sorted), then files (naturally sorted)
    expected_order = [
        "dir2",  # directories first, naturally sorted
        "dir10",
        "dir100",
        "file2.txt",  # files second, naturally sorted
        "file10.txt",
        "file100.txt",
    ]

    assert result_names == expected_order


@pytest.mark.skipif(
    sys.version_info <= (3, 12), reason="Only works with Python 3.12+"
)
def test_extended_path_class(tmp_path: Path) -> None:
    class CustomPath(Path):
        pass

    (tmp_path / "file.txt").touch()

    fb = file_browser(initial_path=CustomPath(tmp_path), limit=1)
    response = fb._list_directory(
        ListDirectoryArgs(path=str(tmp_path)),
    )
    assert isinstance(response, ListDirectoryResponse)
    for file_info in response.files:
        assert isinstance(file_info["path"], str)

    # Convert the value
    value = fb._convert_value(response.files)
    assert isinstance(value, tuple)
    assert len(value) == 1
    assert isinstance(value[0], FileBrowserFileInfo)
    assert isinstance(value[0].path, CustomPath)

    class CustomPathWithClient(Path):
        def __init__(self, path: Path, client: Optional[Any] = None) -> None:
            super().__init__(path)
            self.client = client

        def resolve(self) -> CustomPathWithClient:
            return CustomPathWithClient(super().resolve(), self.client)

    fb = file_browser(
        initial_path=CustomPathWithClient(tmp_path, "custom_client")
    )
    response = fb._list_directory(
        ListDirectoryArgs(path=str(tmp_path)),
    )
    value = fb._convert_value(response.files)
    assert isinstance(value, tuple)
    assert len(value) == 1
    assert isinstance(value[0], FileBrowserFileInfo)
    assert isinstance(value[0].path, CustomPathWithClient)
    assert value[0].path.client == "custom_client"


def test_validation() -> None:
    with pytest.raises(ValueError) as e:
        file_browser(initial_path="invalid", selection_mode="invalid")
    assert "Value must be one of" in str(e.value)
