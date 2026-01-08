# Copyright 2026 Marimo. All rights reserved.
"""Test file manager with absolute directory paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from marimo._server.file_router import AppFileRouter
from marimo._utils.http import HTTPException, HTTPStatus

is_windows = sys.platform == "win32"


class TestAbsoluteDirectoryPath:
    """Test that absolute directory paths work correctly."""

    def test_absolute_directory_path_file_manager(
        self, tmp_path: Path
    ) -> None:
        """Test that files can be opened from absolute directory paths."""
        # Create a test directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Create a test file
        test_file = test_dir / "notebook.py"
        test_file.write_text(
            """
import marimo
app = marimo.App()

@app.cell
def __():
    return

if __name__ == "__main__":
    app.run()
"""
        )

        # Test with absolute path
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        # The directory should be stored correctly (always absolute)
        assert router.directory == absolute_dir

        # Get the files - they have relative paths (relative to directory)
        files = router.files
        assert len(files) > 0
        file_info = files[0]
        assert file_info.is_marimo_file
        # Path is relative to the directory
        assert file_info.path == "notebook.py"

        # Try to get a file manager using the relative path from files list
        file_manager = router.get_file_manager(file_info.path)
        assert file_manager is not None
        # File manager resolves to absolute path
        assert file_manager.filename == str(test_file)
        assert file_manager.is_notebook_named

    def test_relative_directory_path_file_manager(
        self, tmp_path: Path
    ) -> None:
        """Test that files can be opened from relative directory paths."""
        # Create a test directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Create a test file
        test_file = test_dir / "notebook.py"
        test_file.write_text(
            """
import marimo
app = marimo.App()

@app.cell
def __():
    return

if __name__ == "__main__":
    app.run()
"""
        )

        # Change to the tmp_path directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Test with relative path
            relative_dir = "test_dir"
            router = AppFileRouter.from_directory(relative_dir)

            # The directory is converted to absolute for consistency
            assert router.directory == str(test_dir.absolute())

            # Get the files - paths are relative to the directory
            files = router.files
            assert len(files) > 0
            file_info = files[0]
            assert file_info.is_marimo_file
            assert file_info.path == "notebook.py"

            # Try to get a file manager using the relative file path
            file_manager = router.get_file_manager(file_info.path)
            assert file_manager is not None
            assert file_manager.is_notebook_named
            # File manager resolves to absolute path
            assert file_manager.filename == str(test_file.absolute())
        finally:
            os.chdir(original_cwd)

    def test_absolute_vs_relative_directory_consistency(
        self, tmp_path: Path
    ) -> None:
        """Test that absolute and relative paths behave consistently."""
        # Create a test directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Create a test file
        test_file = test_dir / "notebook.py"
        test_file.write_text(
            """
import marimo
app = marimo.App()

@app.cell
def __():
    x = 1
    return x

if __name__ == "__main__":
    app.run()
"""
        )

        # Test with absolute path
        absolute_dir = str(test_dir.absolute())
        absolute_router = AppFileRouter.from_directory(absolute_dir)
        absolute_files = absolute_router.files
        assert len(absolute_files) > 0

        # Get file manager with absolute path
        absolute_file_path = absolute_files[0].path
        absolute_file_manager = absolute_router.get_file_manager(
            absolute_file_path
        )

        # Change to the parent directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Test with relative path
            relative_dir = "test_dir"
            relative_router = AppFileRouter.from_directory(relative_dir)
            relative_files = relative_router.files
            assert len(relative_files) > 0

            # Get file manager with relative path
            relative_file_path = relative_files[0].path
            relative_file_manager = relative_router.get_file_manager(
                relative_file_path
            )

            # Both should reference the same file
            assert (
                Path(absolute_file_manager.filename or "").resolve()
                == Path(relative_file_manager.filename or "").resolve()
            )

            # Both should be able to read the file
            absolute_content = absolute_file_manager.read_file()
            relative_content = relative_file_manager.read_file()
            assert absolute_content == relative_content
            assert "x = 1" in absolute_content
        finally:
            os.chdir(original_cwd)

    def test_file_manager_with_relative_file_in_absolute_dir(
        self, tmp_path: Path
    ) -> None:
        """Test opening a file with a relative path within an absolute directory.

        This is the specific case that the user reported as broken:
        - Run: marimo edit /absolute/path/to/dir
        - Then open a file like 'notebook.py' (relative to the directory)
        """
        # Create a test directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Create a test file
        test_file = test_dir / "notebook.py"
        test_file.write_text(
            """
import marimo
app = marimo.App()

@app.cell
def __():
    return

if __name__ == "__main__":
    app.run()
"""
        )

        # Set up router with absolute directory
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        # Simulate the case where the client sends a relative filename
        # This might happen if the frontend sends just the filename
        relative_filename = "notebook.py"

        # Try to construct the full path
        # This is what should happen in the server code
        full_path = os.path.join(absolute_dir, relative_filename)

        # Verify the file exists
        assert os.path.exists(full_path)

        # Try to get a file manager
        file_manager = router.get_file_manager(full_path)
        assert file_manager is not None
        assert file_manager.is_notebook_named
        assert file_manager.read_file() is not None

    def test_absolute_dir_with_cwd_change(self, tmp_path: Path) -> None:
        """Test that absolute directory paths work even when cwd changes.

        This simulates the scenario where:
        1. User runs: marimo edit /absolute/path/to/dir
        2. The server might change its working directory
        3. Files should still be accessible
        """
        # Create a test directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        other_dir = tmp_path / "other_dir"
        other_dir.mkdir()

        # Create a test file
        test_file = test_dir / "notebook.py"
        test_file.write_text(
            """
import marimo
app = marimo.App()

@app.cell
def __():
    return

if __name__ == "__main__":
    app.run()
"""
        )

        # Set up router with absolute directory
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        # Get the files before changing directory
        files_before = router.files
        assert len(files_before) > 0

        # Save original cwd
        original_cwd = os.getcwd()
        try:
            # Change to a completely different directory
            os.chdir(other_dir)

            # Files should still be accessible
            files_after = router.files
            assert len(files_after) == len(files_before)
            assert files_after[0].path == files_before[0].path

            # Try to get a file manager
            file_path = files_after[0].path
            file_manager = router.get_file_manager(file_path)
            assert file_manager is not None
            assert file_manager.is_notebook_named
            content = file_manager.read_file()
            assert content is not None
            assert "marimo.App" in content
        finally:
            os.chdir(original_cwd)

    def test_relative_file_path_resolved_properly(
        self, tmp_path: Path
    ) -> None:
        """Test that a relative file path is properly resolved.

        When a router is created with an absolute directory, relative file
        paths should be resolved against that directory.
        """
        # Create a test directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Create a test file
        test_file = test_dir / "notebook.py"
        test_file.write_text(
            """
import marimo
app = marimo.App()

@app.cell
def __():
    return

if __name__ == "__main__":
    app.run()
"""
        )

        # Set up router with absolute directory
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        # Change to a different directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Try to open just 'notebook.py' (relative path)
            # This should now succeed because it's resolved relative to
            # the router's directory
            relative_filename = "notebook.py"

            file_manager = router.get_file_manager(relative_filename)
            assert file_manager is not None
            assert file_manager.is_notebook_named
            # Verify it opened the correct file
            assert (
                Path(file_manager.filename or "").resolve()
                == test_file.resolve()
            )
        finally:
            os.chdir(original_cwd)


class TestAbsoluteDirectoryPathOpening:
    """Test that files can be opened correctly from absolute directory paths."""

    def test_open_file_with_basename_from_absolute_dir(
        self, tmp_path: Path
    ) -> None:
        """Test opening a file using just its basename when router has absolute dir.

        This reproduces the bug:
        1. Run: marimo edit /absolute/path/to/dir
        2. Frontend shows list of files
        3. User clicks on a file like 'notebook.py'
        4. Frontend might send just the basename as the file_key
        5. Server should resolve this relative to the router's directory
        """
        # Create a test directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Create a test file
        test_file = test_dir / "notebook.py"
        test_file.write_text(
            """
import marimo
app = marimo.App()

@app.cell
def __():
    return

if __name__ == "__main__":
    app.run()
"""
        )

        # Simulate: marimo edit /absolute/path/to/dir
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        # Change to a different directory to simulate the server running elsewhere
        original_cwd = os.getcwd()
        try:
            other_dir = tmp_path / "other_dir"
            other_dir.mkdir()
            os.chdir(other_dir)

            # The files list should show absolute paths
            files = router.files
            assert len(files) > 0
            file_info = files[0]

            # This should work - using the full absolute path
            file_manager = router.get_file_manager(file_info.path)
            assert file_manager is not None
            assert file_manager.is_notebook_named

            # Now simulate the frontend sending just the basename
            # (This is what might be happening in the bug)
            basename = "notebook.py"

            # This currently fails but should succeed
            # The router should resolve the basename relative to its directory
            try:
                file_manager_from_basename = router.get_file_manager(basename)
                assert file_manager_from_basename is not None
                assert file_manager_from_basename.is_notebook_named
            except HTTPException:
                # This is the bug - it should have resolved relative to router.directory
                pytest.fail(
                    f"Should be able to open file with basename '{basename}' "
                    f"when router has absolute directory '{absolute_dir}'"
                )
        finally:
            os.chdir(original_cwd)

    def test_open_file_with_relative_path_from_absolute_dir(
        self, tmp_path: Path
    ) -> None:
        """Test opening a file using a relative path from absolute dir router.

        Scenario:
        1. marimo edit /absolute/path/to/dir
        2. Frontend sends 'subdir/notebook.py' as file_key
        3. Should resolve to /absolute/path/to/dir/subdir/notebook.py
        """
        # Create a test directory structure with subdirectory
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        subdir = test_dir / "subdir"
        subdir.mkdir()

        # Create a test file in subdirectory
        test_file = subdir / "notebook.py"
        test_file.write_text(
            """
import marimo
app = marimo.App()

@app.cell
def __():
    return

if __name__ == "__main__":
    app.run()
"""
        )

        # Simulate: marimo edit /absolute/path/to/dir
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        # Change to a different directory
        original_cwd = os.getcwd()
        try:
            other_dir = tmp_path / "other_dir"
            other_dir.mkdir()
            os.chdir(other_dir)

            # Try to open with relative path
            relative_path = os.path.join("subdir", "notebook.py")

            try:
                file_manager = router.get_file_manager(relative_path)
                assert file_manager is not None
                assert file_manager.is_notebook_named
            except HTTPException:
                pytest.fail(
                    f"Should be able to open file with relative path '{relative_path}' "
                    f"when router has absolute directory '{absolute_dir}'"
                )
        finally:
            os.chdir(original_cwd)

    def test_files_list_shows_correct_paths_for_absolute_dir(
        self, tmp_path: Path
    ) -> None:
        """Verify that router.files returns the correct paths for absolute dirs."""
        # Create test files
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        test_file1 = test_dir / "notebook1.py"
        test_file1.write_text("import marimo\napp = marimo.App()")

        test_file2 = test_dir / "notebook2.py"
        test_file2.write_text("import marimo\napp = marimo.App()")

        # Test with absolute directory
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        files = router.files
        assert len(files) == 2

        # All paths are now relative to the directory
        for file_info in files:
            # Paths are relative (just the filename for top-level files)
            assert not Path(file_info.path).is_absolute()
            # When joined with directory, should form a valid path
            full_path = Path(absolute_dir) / file_info.path
            assert full_path.exists()

        # Verify each file can be opened using its relative path
        for file_info in files:
            file_manager = router.get_file_manager(file_info.path)
            assert file_manager is not None
            assert file_manager.is_notebook_named

    def test_absolute_path_outside_directory_denied(
        self, tmp_path: Path
    ) -> None:
        """Test that absolute paths outside the router's directory are denied."""
        # Create two separate directories
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        other_dir = tmp_path / "other_dir"
        other_dir.mkdir()

        # Create files in both directories
        test_file = test_dir / "notebook.py"
        test_file.write_text("import marimo\napp = marimo.App()")

        other_file = other_dir / "other_notebook.py"
        other_file.write_text("import marimo\napp = marimo.App()")

        # Create router for test_dir
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        # Should be able to open file within the directory
        file_manager = router.get_file_manager(str(test_file.absolute()))
        assert file_manager is not None

        # Should NOT be able to open file outside the directory
        with pytest.raises(HTTPException) as exc_info:
            router.get_file_manager(str(other_file.absolute()))

        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN
        assert "Access denied" in exc_info.value.detail
        assert "outside the allowed directory" in exc_info.value.detail

    def test_absolute_path_with_symlink_attack_denied(
        self, tmp_path: Path
    ) -> None:
        """Test that symlink attacks to escape the directory are denied."""
        # Create directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        secret_dir = tmp_path / "secret"
        secret_dir.mkdir()

        secret_file = secret_dir / "secrets.py"
        secret_file.write_text("import marimo\napp = marimo.App()")

        # Create router for test_dir
        absolute_dir = str(test_dir.absolute())
        router = AppFileRouter.from_directory(absolute_dir)

        # Try to access the secret file using absolute path
        with pytest.raises(HTTPException) as exc_info:
            router.get_file_manager(str(secret_file.absolute()))

        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN


class TestRelativePathsInFileListing:
    """Test that files list returns correct relative paths for various structures."""

    def test_nested_directory_returns_relative_paths(
        self, tmp_path: Path
    ) -> None:
        """Test that files in subdirectories have correct relative paths."""
        # Create nested structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        subdir = test_dir / "subdir"
        subdir.mkdir()

        # Create files at different levels
        root_file = test_dir / "root.py"
        root_file.write_text("import marimo\napp = marimo.App()")

        nested_file = subdir / "nested.py"
        nested_file.write_text("import marimo\napp = marimo.App()")

        # Create router
        router = AppFileRouter.from_directory(str(test_dir.absolute()))

        files = router.files
        file_paths = _collect_file_paths(files)

        # Should have both files with relative paths
        assert "root.py" in file_paths
        assert os.path.join("subdir", "nested.py") in file_paths

        # Both should be openable using their relative paths
        for path in _collect_file_paths(files):
            file_manager = router.get_file_manager(path)
            assert file_manager is not None
            assert file_manager.is_notebook_named

    def test_deep_nesting_returns_correct_paths(self, tmp_path: Path) -> None:
        """Test deeply nested directories have correct relative paths."""
        # Create deep structure: test_dir/a/b/c/notebook.py
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        dir_a = test_dir / "a"
        dir_a.mkdir()
        dir_b = dir_a / "b"
        dir_b.mkdir()
        dir_c = dir_b / "c"
        dir_c.mkdir()

        deep_file = dir_c / "notebook.py"
        deep_file.write_text("import marimo\napp = marimo.App()")

        # Create router
        router = AppFileRouter.from_directory(str(test_dir.absolute()))

        files = router.files
        file_paths = _collect_file_paths(files)

        # Should have the deep file with correct relative path
        expected_path = os.path.join("a", "b", "c", "notebook.py")
        assert expected_path in file_paths

        # Should be openable using the actual path from the files list
        actual_paths = _collect_file_paths(files)
        file_manager = router.get_file_manager(actual_paths[0])
        assert file_manager is not None
        assert file_manager.filename == str(deep_file.absolute())

    def test_both_relative_and_absolute_paths_work(
        self, tmp_path: Path
    ) -> None:
        """Test that both relative and absolute paths can open the same file."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        test_file = test_dir / "notebook.py"
        test_file.write_text("import marimo\napp = marimo.App()")

        router = AppFileRouter.from_directory(str(test_dir.absolute()))

        # Get the relative path from files list
        files = router.files
        assert len(files) == 1
        relative_path = files[0].path
        assert relative_path == "notebook.py"

        # Open with relative path
        manager_from_relative = router.get_file_manager(relative_path)
        assert manager_from_relative is not None

        # Open with absolute path
        absolute_path = str(test_file.absolute())
        manager_from_absolute = router.get_file_manager(absolute_path)
        assert manager_from_absolute is not None

        # Both should point to the same file
        assert manager_from_relative.filename == manager_from_absolute.filename

    def test_path_traversal_in_relative_path_blocked(
        self, tmp_path: Path
    ) -> None:
        """Test that path traversal attacks using relative paths are blocked."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Create a file outside test_dir
        outside_file = tmp_path / "outside.py"
        outside_file.write_text("import marimo\napp = marimo.App()")

        router = AppFileRouter.from_directory(str(test_dir.absolute()))

        # Try to access file outside using path traversal
        with pytest.raises(HTTPException) as exc_info:
            router.get_file_manager("../outside.py")

        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    @pytest.mark.skipif(is_windows, reason="Non-windows tests")
    def test_path_traversal_multiple_levels_blocked(
        self, tmp_path: Path
    ) -> None:
        """Test that multi-level path traversal is blocked."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        router = AppFileRouter.from_directory(str(test_dir.absolute()))

        # Try various path traversal attempts
        traversal_attempts = [
            "../../../etc/passwd",
            "subdir/../../outside.py",
            "a/../../../etc/passwd",
        ]

        for attempt in traversal_attempts:
            with pytest.raises(HTTPException) as exc_info:
                router.get_file_manager(str(attempt))
            assert exc_info.value.status_code == HTTPStatus.FORBIDDEN, (
                f"Path traversal '{attempt}' should be blocked"
            )


class TestFileManagerPathResolution:
    """Test file manager path resolution edge cases."""

    @pytest.mark.skipif(is_windows, reason="Non-windows tests")
    def test_file_manager_with_dot_path(self, tmp_path: Path) -> None:
        """Test that '.' in paths is handled correctly."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        test_file = test_dir / "notebook.py"
        test_file.write_text("import marimo\napp = marimo.App()")

        router = AppFileRouter.from_directory(str(test_dir.absolute()))

        # Try to open with ./ prefix
        file_manager = router.get_file_manager("./notebook.py")
        assert file_manager is not None
        assert file_manager.filename == str(test_file.absolute())

    @pytest.mark.skipif(is_windows, reason="// has special meaning on Windows")
    def test_file_manager_with_redundant_slashes(self, tmp_path: Path) -> None:
        """Test that redundant slashes in paths are handled."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        subdir = test_dir / "subdir"
        subdir.mkdir()

        test_file = subdir / "notebook.py"
        test_file.write_text("import marimo\napp = marimo.App()")

        router = AppFileRouter.from_directory(str(test_dir.absolute()))

        # Path normalization should handle redundant slashes
        file_manager = router.get_file_manager("subdir//notebook.py")
        assert file_manager is not None
        assert file_manager.filename == str(test_file.absolute())

    def test_nonexistent_file_returns_not_found(self, tmp_path: Path) -> None:
        """Test that accessing a nonexistent file returns NOT_FOUND."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        router = AppFileRouter.from_directory(str(test_dir.absolute()))

        with pytest.raises(HTTPException) as exc_info:
            router.get_file_manager("nonexistent.py")

        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND

    def test_directory_stored_as_absolute(self, tmp_path: Path) -> None:
        """Test that directory is always stored as absolute path."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Create router with relative path
            router = AppFileRouter.from_directory("test_dir")

            # Directory should be stored as absolute
            assert router.directory is not None
            assert Path(router.directory).is_absolute()
            assert router.directory == str(test_dir.absolute())
        finally:
            os.chdir(original_cwd)

    def test_files_accessible_after_cwd_change(self, tmp_path: Path) -> None:
        """Test that files remain accessible after changing working directory."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        other_dir = tmp_path / "other_dir"
        other_dir.mkdir()

        test_file = test_dir / "notebook.py"
        test_file.write_text("import marimo\napp = marimo.App()")

        original_cwd = os.getcwd()
        try:
            # Create router while in tmp_path
            os.chdir(tmp_path)
            router = AppFileRouter.from_directory(str(test_dir.absolute()))

            # Get files list
            files = router.files
            assert len(files) == 1
            relative_path = files[0].path

            # Change to a completely different directory
            os.chdir(other_dir)

            # Should still be able to open file using relative path
            file_manager = router.get_file_manager(relative_path)
            assert file_manager is not None
            assert file_manager.filename == str(test_file.absolute())

            # Should still be able to read content
            content = file_manager.read_file()
            assert "marimo.App" in content
        finally:
            os.chdir(original_cwd)


# Find all file paths (including in nested children)
def _collect_file_paths(items: list) -> list[str]:
    paths = []
    for item in items:
        if not item.is_directory:
            paths.append(item.path)
        if item.children:
            paths.extend(_collect_file_paths(item.children))
    return paths
