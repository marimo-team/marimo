"""Tests for file_pattern functionality in file_browser."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from marimo._plugins.ui._impl.file_browser import (
    ListDirectoryArgs,
    ListDirectoryResponse,
    file_browser,
)


def _file_names(response: ListDirectoryResponse) -> list[str]:
    files = response.files
    return [f["name"] for f in files if not f["is_directory"]]


def _dir_names(response: ListDirectoryResponse) -> list[str]:
    files = response.files
    return [f["name"] for f in files if f["is_directory"]]


def test_file_pattern_regex_basic(tmp_path: Path) -> None:
    (tmp_path / "test.log").touch()
    (tmp_path / "test.txt").touch()
    (tmp_path / "error.log").touch()
    (tmp_path / "readme.md").touch()

    fb = file_browser(initial_path=tmp_path, file_pattern=r".*\.log$")
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert set(_file_names(response)) == {"test.log", "error.log"}


def test_file_pattern_callback_basic(tmp_path: Path) -> None:
    """Callback filtering applies to files."""
    (tmp_path / "small.txt").write_text("x" * 100)
    (tmp_path / "large.txt").write_text("x" * 5000)
    (tmp_path / "medium.txt").write_text("x" * 1000)

    fb = file_browser(
        initial_path=tmp_path,
        file_pattern=lambda p: p.stat().st_size > 500,
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert set(_file_names(response)) == {"large.txt", "medium.txt"}


def test_file_pattern_combined_with_filetypes(tmp_path: Path) -> None:
    (tmp_path / "data_2024.csv").touch()
    (tmp_path / "data_2023.csv").touch()
    (tmp_path / "data_2024.txt").touch()
    (tmp_path / "data_2023.txt").touch()
    (tmp_path / "summary.csv").touch()

    fb = file_browser(
        initial_path=tmp_path,
        filetypes=[".csv"],
        file_pattern=r".*2024.*",
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert _file_names(response) == ["data_2024.csv"]


def test_file_pattern_callback_filters_directories(tmp_path: Path) -> None:
    """Callback filtering applies to directories too."""
    (tmp_path / "dir_visible").mkdir()
    (tmp_path / "dir_hidden").mkdir()
    (tmp_path / "file.txt").touch()

    def filter_hidden(item: Path) -> bool:
        if item.is_dir():
            return "hidden" not in item.name
        return True

    fb = file_browser(initial_path=tmp_path, file_pattern=filter_hidden)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert "dir_visible" in _dir_names(response)
    assert "dir_hidden" not in _dir_names(response)


def test_file_pattern_invalid_regex(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid regex pattern"):
        file_browser(initial_path=tmp_path, file_pattern=r"[invalid(")


def test_file_pattern_invalid_type(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError, match="file_pattern must be a string \(regex\) or callable"
    ):
        file_browser(initial_path=tmp_path, file_pattern=123)  # type: ignore[arg-type]


def test_file_pattern_with_ignore_empty_dirs(tmp_path: Path) -> None:
    txt_dir = tmp_path / "txt_only"
    txt_dir.mkdir()
    (txt_dir / "file.txt").touch()

    log_dir = tmp_path / "log_only"
    log_dir.mkdir()
    (log_dir / "file.log").touch()

    (tmp_path / "empty").mkdir()

    fb = file_browser(
        initial_path=tmp_path,
        file_pattern=r".*\.txt$",
        ignore_empty_dirs=True,
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    dir_names = _dir_names(response)
    assert "txt_only" in dir_names
    assert "log_only" not in dir_names
    assert "empty" not in dir_names


def test_file_pattern_callback_with_exception(tmp_path: Path) -> None:
    (tmp_path / "accessible.txt").touch()
    (tmp_path / "restricted.txt").touch()

    def problematic_callback(p: Path) -> bool:
        if p.name == "restricted.txt":
            raise PermissionError("Cannot access")
        return True

    fb = file_browser(initial_path=tmp_path, file_pattern=problematic_callback)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    file_names = _file_names(response)
    assert "accessible.txt" in file_names
    assert "restricted.txt" not in file_names


def test_file_pattern_complex_regex(tmp_path: Path) -> None:
    (tmp_path / "report_2024-01-15.pdf").touch()
    (tmp_path / "report_2024-02-20.pdf").touch()
    (tmp_path / "report_2023-12-01.pdf").touch()
    (tmp_path / "data.csv").touch()
    (tmp_path / "notes.txt").touch()

    fb = file_browser(
        initial_path=tmp_path,
        file_pattern=r"report_2024-\d{2}-\d{2}\.pdf$",
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert set(_file_names(response)) == {
        "report_2024-01-15.pdf",
        "report_2024-02-20.pdf",
    }


def test_file_pattern_case_sensitivity(tmp_path: Path) -> None:
    (tmp_path / "Test.LOG").touch()
    (tmp_path / "test.log").touch()
    (tmp_path / "TEST.Log").touch()

    fb = file_browser(initial_path=tmp_path, file_pattern=r".*\.log$")
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    assert _file_names(response) == ["test.log"]

    fb_ci = file_browser(
        initial_path=tmp_path,
        file_pattern=r"(?i).*\.log$",
    )
    response_ci = fb_ci._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    assert set(_file_names(response_ci)) == {"Test.LOG", "test.log", "TEST.Log"}


def test_file_pattern_only_files_not_directories(tmp_path: Path) -> None:
    (tmp_path / "test.log").touch()
    (tmp_path / "test.log.backup").mkdir()
    (tmp_path / "other.txt").touch()

    fb = file_browser(initial_path=tmp_path, file_pattern=r".*\.log$")
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert _file_names(response) == ["test.log"]
    assert "test.log.backup" in _dir_names(response)


def test_file_pattern_with_selection_mode_directory(tmp_path: Path) -> None:
    """Directory mode should still honor callback-based directory filtering."""
    good_dir = tmp_path / "good_dir"
    good_dir.mkdir()
    (good_dir / "file.txt").touch()

    bad_dir = tmp_path / "bad_dir"
    bad_dir.mkdir()
    (bad_dir / "file.txt").touch()

    (tmp_path / "file.txt").touch()

    def filter_dirs(item: Path) -> bool:
        if item.is_dir():
            return "good" in item.name
        return True

    fb = file_browser(
        initial_path=tmp_path,
        selection_mode="directory",
        file_pattern=filter_dirs,
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    for item in response.files:
        assert item["is_directory"] is True

    assert _dir_names(response) == ["good_dir"]
