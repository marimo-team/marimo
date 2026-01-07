# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from marimo._utils.paths import normalize_path


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
