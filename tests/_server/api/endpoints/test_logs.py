# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._server.api.endpoints.logs import (
    list_log_files_in_directory,
    read_log_file,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_list_log_files_empty(tmp_path: Path) -> None:
    assert list_log_files_in_directory(tmp_path) == []


def test_list_log_files_nonexistent(tmp_path: Path) -> None:
    assert list_log_files_in_directory(tmp_path / "nonexistent") == []


def test_list_log_files(tmp_path: Path) -> None:
    (tmp_path / "marimo.log").write_text("log content")
    (tmp_path / "other.log").write_text("other content")
    # Rotated backup should be excluded (suffix is not .log)
    (tmp_path / "marimo.log.2026-02-13").write_text("old content")
    # Non-log file should be excluded
    (tmp_path / "readme.txt").write_text("readme")

    result = list_log_files_in_directory(tmp_path)
    assert result == ["marimo.log", "other.log"]


def test_read_log_file(tmp_path: Path) -> None:
    (tmp_path / "marimo.log").write_text("line1\nline2\nline3\n")
    content, status = read_log_file(tmp_path, "marimo.log")
    assert status == 200
    assert content == "line1\nline2\nline3\n"


def test_read_log_file_not_found(tmp_path: Path) -> None:
    content, status = read_log_file(tmp_path, "nonexistent.log")
    assert status == 404


def test_read_log_file_path_traversal(tmp_path: Path) -> None:
    content, status = read_log_file(tmp_path, "../../etc/passwd")
    assert status == 400

    content, status = read_log_file(tmp_path, "foo/bar.log")
    assert status == 400

    content, status = read_log_file(tmp_path, "foo\\bar.log")
    assert status == 400


def test_read_log_file_truncates(tmp_path: Path) -> None:
    lines = [f"line {i}\n" for i in range(1000)]
    (tmp_path / "big.log").write_text("".join(lines))
    content, status = read_log_file(tmp_path, "big.log")
    assert status == 200
    assert content is not None
    # Should only have the last 500 lines
    result_lines = content.splitlines()
    assert len(result_lines) == 500
    assert result_lines[0] == "line 500"
    assert result_lines[-1] == "line 999"
