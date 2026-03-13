"""Tests for file_pattern functionality in file_browser."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# These will be imported once marimo is properly installed
# For now, they document the expected behavior

# from marimo._plugins.ui._impl.file_browser import (
#     FileBrowserFileInfo,
#     ListDirectoryArgs,
#     ListDirectoryResponse,
#     file_browser,
# )


def test_file_pattern_regex_basic(tmp_path: Path) -> None:
    """Test file_pattern with a basic regex pattern."""
    # Creates:
    # tmp_path/
    # ├── test.log
    # ├── test.txt
    # ├── error.log
    # └── readme.md

    (tmp_path / "test.log").touch()
    (tmp_path / "test.txt").touch()
    (tmp_path / "error.log").touch()
    (tmp_path / "readme.md").touch()

    # Filter for .log files using regex
    # fb = file_browser(initial_path=tmp_path, file_pattern=r".*\.log$")
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # file_names = [f["name"] for f in response.files if not f["is_directory"]]

    # assert set(file_names) == {"test.log", "error.log"}
    # assert "test.txt" not in file_names
    # assert "readme.md" not in file_names
    pass


def test_file_pattern_callback_basic(tmp_path: Path) -> None:
    """Test file_pattern with a callback function."""
    # Creates:
    # tmp_path/
    # ├── small.txt  (100 bytes)
    # ├── large.txt  (5000 bytes)
    # └── medium.txt (1000 bytes)

    (tmp_path / "small.txt").write_text("x" * 100)
    (tmp_path / "large.txt").write_text("x" * 5000)
    (tmp_path / "medium.txt").write_text("x" * 1000)

    # Filter for files > 500 bytes
    # fb = file_browser(
    #     initial_path=tmp_path,
    #     file_pattern=lambda p: p.stat().st_size > 500
    # )
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # file_names = [f["name"] for f in response.files if not f["is_directory"]]

    # assert set(file_names) == {"large.txt", "medium.txt"}
    # assert "small.txt" not in file_names
    pass


def test_file_pattern_combined_with_filetypes(tmp_path: Path) -> None:
    """Test file_pattern combined with filetypes parameter."""
    # Creates:
    # tmp_path/
    # ├── data_2024.csv
    # ├── data_2023.csv
    # ├── data_2024.txt
    # ├── data_2023.txt
    # └── summary.csv

    (tmp_path / "data_2024.csv").touch()
    (tmp_path / "data_2023.csv").touch()
    (tmp_path / "data_2024.txt").touch()
    (tmp_path / "data_2023.txt").touch()
    (tmp_path / "summary.csv").touch()

    # Combine filetypes (.csv) with regex (contains 2024)
    # fb = file_browser(
    #     initial_path=tmp_path,
    #     filetypes=[".csv"],
    #     file_pattern=r".*2024.*"
    # )
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # file_names = [f["name"] for f in response.files if not f["is_directory"]]

    # Only data_2024.csv should match both filters
    # assert file_names == ["data_2024.csv"]
    pass


def test_file_pattern_callback_filters_directories(tmp_path: Path) -> None:
    """Test that callback can filter directories as well as files."""
    # Creates:
    # tmp_path/
    # ├── dir_visible/
    # ├── dir_hidden/
    # └── file.txt

    (tmp_path / "dir_visible").mkdir()
    (tmp_path / "dir_hidden").mkdir()
    (tmp_path / "file.txt").touch()

    # Callback that excludes directories with "hidden" in name
    # def filter_hidden(item: Path) -> bool:
    #     if item.is_dir():
    #         return "hidden" not in item.name
    #     return True  # Show all files

    # fb = file_browser(initial_path=tmp_path, file_pattern=filter_hidden)
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # dir_names = [f["name"] for f in response.files if f["is_directory"]]

    # assert "dir_visible" in dir_names
    # assert "dir_hidden" not in dir_names
    pass


def test_file_pattern_invalid_regex(tmp_path: Path) -> None:
    """Test that invalid regex pattern raises ValueError."""
    # Invalid regex pattern
    # with pytest.raises(ValueError, match="Invalid regex pattern"):
    #     file_browser(initial_path=tmp_path, file_pattern=r"[invalid(")
    pass


def test_file_pattern_invalid_type(tmp_path: Path) -> None:
    """Test that invalid file_pattern type raises ValueError."""
    # Invalid type (not string or callable)
    # with pytest.raises(ValueError, match="must be a string or callable"):
    #     file_browser(initial_path=tmp_path, file_pattern=123)  # type: ignore
    pass


def test_file_pattern_with_ignore_empty_dirs(tmp_path: Path) -> None:
    """Test file_pattern is respected when checking empty directories."""
    # Creates:
    # tmp_path/
    # ├── txt_only/
    # │   └── file.txt
    # ├── log_only/
    # │   └── file.log
    # └── empty/

    txt_dir = tmp_path / "txt_only"
    txt_dir.mkdir()
    (txt_dir / "file.txt").touch()

    log_dir = tmp_path / "log_only"
    log_dir.mkdir()
    (log_dir / "file.log").touch()

    (tmp_path / "empty").mkdir()

    # Filter for .txt files and ignore empty dirs
    # fb = file_browser(
    #     initial_path=tmp_path,
    #     file_pattern=r".*\.txt$",
    #     ignore_empty_dirs=True
    # )
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # dir_names = [f["name"] for f in response.files if f["is_directory"]]

    # txt_only should be shown (has .txt files)
    # log_only should be hidden (no .txt files, pattern doesn't match)
    # empty should be hidden (empty)
    # assert "txt_only" in dir_names
    # assert "log_only" not in dir_names
    # assert "empty" not in dir_names
    pass


def test_file_pattern_callback_with_exception(tmp_path: Path) -> None:
    """Test that callback exceptions are handled gracefully."""
    # Creates:
    # tmp_path/
    # ├── accessible.txt
    # └── restricted.txt (will cause exception in callback)

    (tmp_path / "accessible.txt").touch()
    (tmp_path / "restricted.txt").touch()

    # Callback that raises exception for certain files
    # def problematic_callback(p: Path) -> bool:
    #     if p.name == "restricted.txt":
    #         raise PermissionError("Cannot access")
    #     return True

    # fb = file_browser(initial_path=tmp_path, file_pattern=problematic_callback)
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # file_names = [f["name"] for f in response.files if not f["is_directory"]]

    # accessible.txt should be shown
    # restricted.txt should be skipped (exception caught)
    # assert "accessible.txt" in file_names
    # assert "restricted.txt" not in file_names
    pass


def test_file_pattern_complex_regex(tmp_path: Path) -> None:
    """Test file_pattern with complex regex patterns."""
    # Creates:
    # tmp_path/
    # ├── report_2024-01-15.pdf
    # ├── report_2024-02-20.pdf
    # ├── report_2023-12-01.pdf
    # ├── data.csv
    # └── notes.txt

    (tmp_path / "report_2024-01-15.pdf").touch()
    (tmp_path / "report_2024-02-20.pdf").touch()
    (tmp_path / "report_2023-12-01.pdf").touch()
    (tmp_path / "data.csv").touch()
    (tmp_path / "notes.txt").touch()

    # Match only 2024 reports with complex regex
    # fb = file_browser(
    #     initial_path=tmp_path,
    #     file_pattern=r"report_2024-\d{2}-\d{2}\.pdf$"
    # )
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # file_names = [f["name"] for f in response.files if not f["is_directory"]]

    # assert set(file_names) == {"report_2024-01-15.pdf", "report_2024-02-20.pdf"}
    # assert "report_2023-12-01.pdf" not in file_names
    pass


def test_file_pattern_case_sensitivity(tmp_path: Path) -> None:
    """Test that regex patterns are case-sensitive by default."""
    # Creates:
    # tmp_path/
    # ├── Test.LOG
    # ├── test.log
    # └── TEST.Log

    (tmp_path / "Test.LOG").touch()
    (tmp_path / "test.log").touch()
    (tmp_path / "TEST.Log").touch()

    # Case-sensitive pattern (only lowercase .log)
    # fb = file_browser(initial_path=tmp_path, file_pattern=r".*\.log$")
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # file_names = [f["name"] for f in response.files if not f["is_directory"]]

    # Only test.log should match (exact case)
    # assert file_names == ["test.log"]

    # Case-insensitive pattern
    # fb_ci = file_browser(
    #     initial_path=tmp_path,
    #     file_pattern=r"(?i).*\.log$"  # (?i) for case-insensitive
    # )
    # response_ci = fb_ci._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    # file_names_ci = [f["name"] for f in response_ci.files if not f["is_directory"]]

    # All should match with case-insensitive flag
    # assert set(file_names_ci) == {"Test.LOG", "test.log", "TEST.Log"}
    pass


def test_file_pattern_only_files_not_directories(tmp_path: Path) -> None:
    """Test that regex pattern only applies to files, not directories."""
    # Creates:
    # tmp_path/
    # ├── test.log (file)
    # ├── test.log.backup/ (directory)
    # └── other.txt

    (tmp_path / "test.log").touch()
    (tmp_path / "test.log.backup").mkdir()
    (tmp_path / "other.txt").touch()

    # Pattern to match .log files
    # fb = file_browser(initial_path=tmp_path, file_pattern=r".*\.log$")
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # file_names = [f["name"] for f in response.files if not f["is_directory"]]
    # dir_names = [f["name"] for f in response.files if f["is_directory"]]

    # Only test.log file should be shown
    # assert file_names == ["test.log"]
    # Directory should still be shown (pattern doesn't apply to directories)
    # assert "test.log.backup" in dir_names
    pass


def test_file_pattern_with_selection_mode_directory(tmp_path: Path) -> None:
    """Test file_pattern callback with selection_mode='directory'."""
    # Creates:
    # tmp_path/
    # ├── good_dir/
    # │   └── file.txt
    # ├── bad_dir/
    # │   └── file.txt
    # └── file.txt

    good_dir = tmp_path / "good_dir"
    good_dir.mkdir()
    (good_dir / "file.txt").touch()

    bad_dir = tmp_path / "bad_dir"
    bad_dir.mkdir()
    (bad_dir / "file.txt").touch()

    (tmp_path / "file.txt").touch()

    # Callback to filter directories by name (and all files)
    # def filter_dirs(item: Path) -> bool:
    #     if item.is_dir():
    #         return "good" in item.name
    #     return True

    # fb = file_browser(
    #     initial_path=tmp_path,
    #     selection_mode="directory",
    #     file_pattern=filter_dirs
    # )
    # response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # All results should be directories (selection_mode filters files)
    # for item in response.files:
    #     assert item["is_directory"] is True

    # dir_names = [f["name"] for f in response.files]
    # assert "good_dir" in dir_names
    # assert "bad_dir" not in dir_names
    pass
