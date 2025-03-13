from __future__ import annotations

import sys
import tempfile
from pathlib import Path

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
        assert isinstance(fb.initial_path, Path)
        assert str(fb.initial_path) == str(Path(temp_dir).resolve())
        assert fb.selection_mode == "file"
        assert fb.filetypes == set()
        assert fb.restrict_navigation is False

        # Test with custom filetypes
        custom_filetypes = [".txt", ".csv"]
        fb = file_browser(
            initial_path=temp_dir,
            filetypes=custom_filetypes,
            selection_mode="directory",
            restrict_navigation=True,
        )
        assert fb.initial_path == Path(temp_dir).resolve()
        assert fb.filetypes == set(custom_filetypes)
        assert fb.selection_mode == "directory"
        assert fb.restrict_navigation is True


def test_list_directory() -> None:
    fb = file_browser(
        initial_path=Path.cwd(), filetypes=[".txt"], selection_mode="file"
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(Path.cwd())))
    assert isinstance(response, ListDirectoryResponse)
    for file_info in response.files:
        assert file_info["is_directory"] or file_info["path"].endswith(
            tuple(fb.filetypes)
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
            path="/some/path/file.txt",
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
            path="/some/path/file.txt",
            name="file.txt",
            is_directory=False,
        )
    ]
    assert fb.path(0) == "/some/path/file.txt"
    assert fb.path(1) is None


@pytest.mark.skipif(
    sys.version_info <= (3, 11), reason="Only works with Python 3.12+"
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
