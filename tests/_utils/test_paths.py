# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from marimo._utils.paths import normalize_path, pretty_path


def test_normalize_path_makes_absolute() -> None:
    """Test that relative paths are converted to absolute paths."""
    relative_path = Path("foo") / "bar"
    result = normalize_path(relative_path)

    assert result.is_absolute()
    assert result == Path.cwd() / "foo" / "bar"


def test_normalize_path_removes_parent_and_current_refs() -> None:
    """Test that .. and . components are normalized."""
    path_with_refs = Path("foo") / "bar" / ".." / "baz" / "." / "qux"
    result = normalize_path(path_with_refs)

    assert result.is_absolute()
    assert ".." not in str(result)
    assert str(result) == str(Path.cwd() / "foo" / "baz" / "qux")


def test_normalize_path_handles_already_absolute() -> None:
    """Test that absolute paths stay absolute and get normalized."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        # Create a path with .. in absolute path
        absolute_with_parents = temp_path / "foo" / "bar" / ".." / "baz"
        result = normalize_path(absolute_with_parents)

        assert result.is_absolute()
        assert ".." not in str(result)
        # Should resolve to temp_path/foo/baz
        assert result == temp_path / "foo" / "baz"


def test_normalize_path_does_not_resolve_symlinks() -> None:
    """Test that symlinks are NOT resolved (key security feature)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create a real directory
        real_dir = temp_path / "real_directory"
        real_dir.mkdir()

        # Create a file in the real directory
        real_file = real_dir / "test.txt"
        real_file.write_text("test content")

        # Create a symlink to the real directory
        symlink_dir = temp_path / "symlinked_directory"
        try:
            symlink_dir.symlink_to(real_dir)
        except OSError:
            # On Windows, creating symlinks might require admin privileges
            pytest.skip("Cannot create symlinks on this system")

        # Path through symlink
        path_through_symlink = symlink_dir / "test.txt"

        # normalize_path should NOT resolve the symlink
        normalized = normalize_path(path_through_symlink)

        # Should contain the symlink name, not the real directory
        assert "symlinked_directory" in str(normalized)
        assert "real_directory" not in str(normalized)

        # Compare with resolve() which DOES follow symlinks
        resolved = path_through_symlink.resolve()
        assert "real_directory" in str(resolved)

        # They should be different
        assert normalized != resolved


class TestPrettyPath:
    """Tests for pretty_path function."""

    def test_empty_filename_returns_empty(self) -> None:
        """Test that empty string returns empty string."""
        assert pretty_path("") == ""

    def test_relative_path_unchanged(self) -> None:
        """Test that relative paths are returned unchanged."""
        assert pretty_path("foo/bar.py") == "foo/bar.py"

    def test_absolute_path_inside_cwd_becomes_relative(self) -> None:
        """Test that absolute paths inside CWD become relative."""
        cwd = Path.cwd()
        abs_path = str(cwd / "subdir" / "file.py")
        result = pretty_path(abs_path)
        # Should be relative to CWD
        assert result == os.path.join("subdir", "file.py")

    def test_absolute_path_outside_cwd_stays_absolute(self) -> None:
        """Test that absolute paths outside CWD stay absolute."""
        with tempfile.TemporaryDirectory() as tmp:
            # This is outside CWD
            abs_path = os.path.join(tmp, "file.py")
            result = pretty_path(abs_path)
            # Should stay absolute or have .. prefix (depending on location)
            # Either way, it should contain the filename
            assert "file.py" in result

    def test_base_dir_makes_path_relative_to_it(self) -> None:
        """Test that base_dir parameter makes paths relative to that dir."""
        with tempfile.TemporaryDirectory() as tmp:
            subdir = os.path.join(tmp, "subdir")
            os.makedirs(subdir)
            notebook = os.path.join(subdir, "notebook.py")
            Path(notebook).touch()

            # With base_dir pointing to subdir, should return just filename
            result = pretty_path(notebook, base_dir=subdir)
            assert result == "notebook.py"

    def test_base_dir_with_nested_path(self) -> None:
        """Test base_dir with nested subdirectories."""
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, "a", "b", "c")
            os.makedirs(nested)
            notebook = os.path.join(nested, "notebook.py")
            Path(notebook).touch()

            # With base_dir pointing to parent, should return relative path
            result = pretty_path(notebook, base_dir=tmp)
            expected = os.path.join("a", "b", "c", "notebook.py")
            assert result == expected

    def test_base_dir_file_outside_falls_back_to_cwd_relative(self) -> None:
        """Test that files outside base_dir fall back to CWD-relative."""
        with tempfile.TemporaryDirectory() as base:
            with tempfile.TemporaryDirectory() as other:
                # File is in 'other', not in 'base'
                file_path = os.path.join(other, "outside.py")
                Path(file_path).touch()

                result = pretty_path(file_path, base_dir=base)
                # Should contain the filename (exact path depends on CWD)
                assert "outside.py" in result

    def test_base_dir_accepts_path_object(self) -> None:
        """Test that base_dir accepts Path objects."""
        with tempfile.TemporaryDirectory() as tmp:
            subdir = Path(tmp) / "subdir"
            subdir.mkdir()
            notebook = subdir / "notebook.py"
            notebook.touch()

            # Should work with Path object
            result = pretty_path(str(notebook), base_dir=subdir)
            assert result == "notebook.py"

    def test_base_dir_accepts_string(self) -> None:
        """Test that base_dir accepts string paths."""
        with tempfile.TemporaryDirectory() as tmp:
            subdir = os.path.join(tmp, "subdir")
            os.makedirs(subdir)
            notebook = os.path.join(subdir, "notebook.py")
            Path(notebook).touch()

            # Should work with string
            result = pretty_path(notebook, base_dir=subdir)
            assert result == "notebook.py"
