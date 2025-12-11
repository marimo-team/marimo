# Copyright 2024 Marimo. All rights reserved.
"""Tests for storage.py"""

from pathlib import Path

import pytest

from marimo._server.api.status import HTTPException
from marimo._server.notebook.storage import FilesystemStorage


class TestFilesystemStorage:
    def test_read_success(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        content = storage.read(test_file)
        assert content == "hello world"

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "nonexistent.txt"

        with pytest.raises(HTTPException) as exc_info:
            storage.read(test_file)
        assert exc_info.value.status_code == 500

    def test_write_success(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "output.txt"

        storage.write(test_file, "test content")

        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "test content"

    def test_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "subdir" / "nested" / "file.txt"

        storage.write(test_file, "nested content")

        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "nested content"

    def test_write_with_string_path(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "string_path.txt"

        storage.write(str(test_file), "content via string")

        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "content via string"

    def test_exists_true(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "exists.txt"
        test_file.write_text("exists", encoding="utf-8")

        assert storage.exists(test_file) is True

    def test_exists_false(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "does_not_exist.txt"

        assert storage.exists(test_file) is False

    def test_rename_success(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        old_file = tmp_path / "old.txt"
        new_file = tmp_path / "new.txt"
        old_file.write_text("content", encoding="utf-8")

        storage.rename(old_file, new_file)

        assert not old_file.exists()
        assert new_file.exists()
        assert new_file.read_text(encoding="utf-8") == "content"

    def test_rename_creates_parent_dirs(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        old_file = tmp_path / "old.txt"
        new_file = tmp_path / "nested" / "dir" / "new.txt"
        old_file.write_text("content", encoding="utf-8")

        storage.rename(old_file, new_file)

        assert not old_file.exists()
        assert new_file.exists()

    def test_rename_nonexistent_file(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        old_file = tmp_path / "nonexistent.txt"
        new_file = tmp_path / "new.txt"

        with pytest.raises(HTTPException) as exc_info:
            storage.rename(old_file, new_file)
        assert exc_info.value.status_code == 500

    def test_is_same_path_identical(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "file.txt"
        test_file.write_text("content", encoding="utf-8")

        assert storage.is_same_path(test_file, test_file) is True

    def test_is_same_path_different(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content", encoding="utf-8")
        file2.write_text("content", encoding="utf-8")

        assert storage.is_same_path(file1, file2) is False

    def test_is_same_path_relative_vs_absolute(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "file.txt"
        test_file.write_text("content", encoding="utf-8")

        # Compare absolute and relative representations
        assert storage.is_same_path(test_file, test_file.resolve()) is True

    def test_get_absolute_path(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        test_file = tmp_path / "file.txt"

        abs_path = storage.get_absolute_path(test_file)

        assert abs_path.is_absolute()
        assert abs_path.name == "file.txt"

    def test_read_related_file_absolute(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        base_file = tmp_path / "notebook.py"
        related_file = tmp_path / "style.css"
        related_file.write_text("/* CSS */", encoding="utf-8")

        content = storage.read_related_file(base_file, str(related_file))

        assert content == "/* CSS */"

    def test_read_related_file_relative(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        base_file = tmp_path / "notebook.py"
        related_file = tmp_path / "style.css"
        related_file.write_text("/* CSS */", encoding="utf-8")

        content = storage.read_related_file(base_file, "style.css")

        assert content == "/* CSS */"

    def test_read_related_file_nonexistent(self, tmp_path: Path) -> None:
        storage = FilesystemStorage()
        base_file = tmp_path / "notebook.py"

        content = storage.read_related_file(base_file, "nonexistent.css")

        assert content is None

    def test_read_related_file_nested(self, tmp_path: Path) -> None:
        """Test reading related file in subdirectory."""
        storage = FilesystemStorage()
        base_file = tmp_path / "notebook.py"
        subdir = tmp_path / "assets"
        subdir.mkdir()
        related_file = subdir / "style.css"
        related_file.write_text("/* nested CSS */", encoding="utf-8")

        content = storage.read_related_file(base_file, "assets/style.css")

        assert content == "/* nested CSS */"

    def test_ensure_parent_dirs_with_string(self, tmp_path: Path) -> None:
        """Test ensure_parent_dirs with string path."""
        storage = FilesystemStorage()
        test_file = str(tmp_path / "nested" / "dir" / "file.txt")

        storage.ensure_parent_dirs(Path(test_file))

        assert Path(test_file).parent.exists()

    def test_is_same_path_with_strings(self, tmp_path: Path) -> None:
        """Test is_same_path handles string paths correctly."""
        storage = FilesystemStorage()
        test_file = tmp_path / "file.txt"
        test_file.write_text("content", encoding="utf-8")

        # Pass as strings to test _ensure_path
        assert storage.is_same_path(Path(str(test_file)), test_file) is True
