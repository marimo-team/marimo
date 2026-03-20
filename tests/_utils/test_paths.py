# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from marimo._utils.paths import get_marimo_dir, normalize_path, pretty_path


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


def test_normalize_path_skips_cloudpathlib_paths() -> None:
    """Test that cloud paths from cloudpathlib are returned unchanged.

    os.path.normpath corrupts URI schemes like s3:// by reducing them to s3:/
    This test verifies that cloudpathlib paths bypass normalization.
    """
    from unittest.mock import MagicMock

    # Create a mock cloud path that simulates cloudpathlib.S3Path
    # We can't inherit from PurePosixPath because it normalizes on construction
    mock_path = MagicMock()
    mock_path.__class__.__module__ = "cloudpathlib.s3.s3path"

    # normalize_path should return the path unchanged
    result = normalize_path(mock_path)

    # Should be the exact same object, returned unchanged
    assert result is mock_path


def test_normalize_path_does_not_skip_regular_paths() -> None:
    """Test that regular Path objects are still normalized properly."""
    # Ensure the cloudpathlib check doesn't affect regular paths
    relative_path = Path("foo") / "bar"
    result = normalize_path(relative_path)

    # Should be converted to absolute
    assert result.is_absolute()
    # Module should be pathlib, not cloudpathlib
    assert result.__class__.__module__.startswith("pathlib")


class TestGetMarimoDir:
    """Tests for get_marimo_dir function."""

    def test_none_returns_cwd_relative(self) -> None:
        assert get_marimo_dir(None) == Path("__marimo__")

    def test_file_path_returns_sibling_dir(self, tmp_path: Path) -> None:
        notebook = tmp_path / "notebook.py"
        notebook.touch()
        result = get_marimo_dir(str(notebook))
        assert result == tmp_path / "__marimo__"

    def test_directory_path(self, tmp_path: Path) -> None:
        result = get_marimo_dir(tmp_path)
        assert result == tmp_path / "__marimo__"

    def test_pycache_prefix_mirrors_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prefix = tmp_path / "prefix"
        monkeypatch.setattr("sys.pycache_prefix", str(prefix))

        notebook = Path("/app/notebooks/example/foo.py")
        result = get_marimo_dir(str(notebook))
        assert (
            result == prefix / "app" / "notebooks" / "example" / "__marimo__"
        )

    def test_pycache_prefix_not_applied_when_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.pycache_prefix", None)
        notebook = Path("/app/notebooks/foo.py")
        result = get_marimo_dir(str(notebook))
        assert result == Path("/app/notebooks/__marimo__")

    def test_pycache_prefix_ignored_for_none_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.pycache_prefix", str(tmp_path / "prefix"))
        assert get_marimo_dir(None) == Path("__marimo__")

    def test_pycache_prefix_ignored_for_relative_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Relative paths stay notebook-relative, not relocated under prefix."""
        monkeypatch.setattr("sys.pycache_prefix", str(tmp_path / "prefix"))
        result = get_marimo_dir("notebook.py")
        # Should resolve relative to CWD, not under the prefix.
        assert (
            result == normalize_path(Path("notebook.py")).parent / "__marimo__"
        )
        assert str(tmp_path / "prefix") not in str(result)

    def test_pycache_prefix_mkdir_creates_full_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mirrored prefix paths can be created with mkdir(parents=True)."""
        prefix = tmp_path / "prefix"
        monkeypatch.setattr("sys.pycache_prefix", str(prefix))

        notebook = tmp_path / "project" / "notebook.py"
        marimo_dir = get_marimo_dir(str(notebook))
        # The full tree doesn't exist yet — mkdir should still work.
        marimo_dir.mkdir(parents=True, exist_ok=True)
        assert marimo_dir.is_dir()


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
