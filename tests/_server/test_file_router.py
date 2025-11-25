from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.file_router import (
    AppFileRouter,
    LazyListOfFilesAppFileRouter,
    ListOfFilesAppFileRouter,
    NewFileAppFileRouter,
    validate_inside_directory,
)
from marimo._server.models.home import MarimoFile

file_contents = """
import marimo
__generated_with = "0.0.1"
app = marimo.App()
"""


class TestAppFileRouter(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        # Create temporary files
        self.test_file1 = tempfile.NamedTemporaryFile(
            delete=False, dir=self.test_dir, suffix=".py"
        )
        self.test_file2 = tempfile.NamedTemporaryFile(
            delete=False, dir=self.test_dir, suffix=".py"
        )
        self.test_file_3 = tempfile.NamedTemporaryFile(
            delete=False, dir=self.test_dir, suffix=".md"
        )
        # Write to the temporary files
        self.test_file1.write(file_contents.encode())
        self.test_file1.close()
        self.test_file2.write(file_contents.encode())
        self.test_file2.close()
        self.test_file_3.write(b"marimo-version: 0.0.0")
        self.test_file_3.close()

        # Create a nested directory and file
        self.nested_dir = os.path.join(self.test_dir, "nested")
        os.mkdir(self.nested_dir)
        self.nested_file = tempfile.NamedTemporaryFile(
            delete=False, dir=self.nested_dir, suffix=".py"
        )
        self.nested_file.write(file_contents.encode())
        self.nested_file.close()

    def tearDown(self):
        # Clean up temporary files and directory
        os.unlink(self.test_file1.name)
        os.unlink(self.test_file2.name)
        os.unlink(self.test_file_3.name)
        os.unlink(self.nested_file.name)
        shutil.rmtree(self.nested_dir)
        shutil.rmtree(self.test_dir)

    def test_infer_file(self):
        # Test infer method with a file path
        router = AppFileRouter.infer(self.test_file1.name)
        assert isinstance(router, ListOfFilesAppFileRouter)

    def test_infer_directory(self):
        # Test infer method with a directory path
        router = AppFileRouter.infer(self.test_dir)
        assert isinstance(router, LazyListOfFilesAppFileRouter)

    def test_from_files(self):
        # Test creating a router from a list of files
        files = [
            MarimoFile(
                name="test.py",
                path=self.test_file1.name,
                last_modified=os.path.getmtime(self.test_file1.name),
            )
        ]
        router = AppFileRouter.from_files(files)
        assert isinstance(router, ListOfFilesAppFileRouter)

    def test_new_file_router(self):
        # Test the NewFileAppFileRouter
        router = AppFileRouter.new_file()
        assert isinstance(router, NewFileAppFileRouter)
        assert router.maybe_get_single_file() is None

    def test_lazy_list_of_files(self):
        # Test the lazy loading of files in a directory
        router = LazyListOfFilesAppFileRouter(
            self.test_dir, include_markdown=False
        )
        files = router.files
        assert (
            len(files) == 3
        )  # Assuming the directory only contains the two created files

    def test_lazy_list_with_broken_symlinks(self):
        # Test the lazy loading of files in a directory with broken symlinks
        # Create a broken symlink
        broken_symlink = os.path.join(self.test_dir, "broken_symlink.py")
        os.symlink("non_existent_file", broken_symlink)
        router = LazyListOfFilesAppFileRouter(
            self.test_dir, include_markdown=False
        )
        files = router.files
        assert len(files) == 3

        # Remove the broken symlink
        os.unlink(broken_symlink)

    def test_lazy_list_with_markdown(self):
        # Test the lazy loading of files in a directory with markdown
        router = LazyListOfFilesAppFileRouter(
            self.test_dir, include_markdown=True
        )
        # Create markdown files
        files = router.files
        assert len(files) == 4

        # Toggling markdown
        router = router.toggle_markdown(False)
        files = router.files
        assert len(files) == 3

        # Toggle markdown back
        router = router.toggle_markdown(True)
        files = router.files
        assert len(files) == 4

    def test_lazy_list_of_get_app_file_manager(self):
        router = LazyListOfFilesAppFileRouter(
            self.test_dir, include_markdown=False
        )
        filename = self.test_file1.name
        assert os.path.exists(filename), f"File {filename} does not exist"
        file_manager = router.get_file_manager(key=filename)
        assert file_manager.filename == os.path.join(self.test_dir, filename)

    def test_lazy_list_of_get_app_file_manager_nested(self):
        router = LazyListOfFilesAppFileRouter(
            self.test_dir, include_markdown=False
        )
        nested_filename = self.nested_file.name
        file_manager = router.get_file_manager(key=nested_filename)
        assert file_manager.filename == self.nested_file.name
        assert file_manager.filename is not None
        assert os.path.exists(file_manager.filename)
        assert file_manager.filename.startswith(self.test_dir)
        assert "nested" in file_manager.filename


class TestValidateInsideDirectory(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure
        self.test_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_dir) / "test.py"
        self.test_file.write_text("test")

        # Create nested directory
        self.nested_dir = Path(self.test_dir) / "nested"
        self.nested_dir.mkdir()
        self.nested_file = self.nested_dir / "nested.py"
        self.nested_file.write_text("test")

        # Create directory outside test_dir
        self.outside_dir = tempfile.mkdtemp()
        self.outside_file = Path(self.outside_dir) / "outside.py"
        self.outside_file.write_text("test")

        # Save current working directory
        self.original_cwd = os.getcwd()

    def tearDown(self):
        # Clean up
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.outside_dir, ignore_errors=True)
        os.chdir(self.original_cwd)

    def test_absolute_directory_absolute_filepath_inside(self):
        """Test: absolute directory, absolute filepath, file inside directory"""
        directory = Path(self.test_dir).resolve()
        filepath = Path(self.test_file).resolve()
        # Should not raise
        validate_inside_directory(directory, filepath)

    def test_absolute_directory_absolute_filepath_outside(self):
        """Test: absolute directory, absolute filepath, file outside directory"""
        directory = Path(self.test_dir).resolve()
        filepath = Path(self.outside_file).resolve()
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_absolute_directory_relative_filepath_inside(self):
        """Test: absolute directory, relative filepath, file inside directory"""
        directory = Path(self.test_dir).resolve()
        filepath = Path("test.py")
        # Change to test_dir so relative path resolves correctly
        os.chdir(self.test_dir)
        # Should not raise
        validate_inside_directory(directory, filepath)

    def test_absolute_directory_relative_filepath_outside(self):
        """Test: absolute directory, relative filepath, file outside directory"""
        directory = Path(self.test_dir).resolve()
        # When directory is absolute and filepath is relative, filepath is resolved
        # relative to directory. So "outside.py" would resolve to test_dir/outside.py
        # which doesn't exist but would be inside test_dir. To test outside, we need
        # to use a path that goes outside even when resolved relative to directory.
        filepath = Path("..") / ".." / "etc" / "passwd"
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_relative_directory_absolute_filepath_inside(self):
        """Test: relative directory, absolute filepath, file inside directory"""
        os.chdir(self.test_dir)
        directory = Path(".")
        filepath = Path(self.test_file).resolve()
        # Should not raise
        validate_inside_directory(directory, filepath)

    def test_relative_directory_absolute_filepath_outside(self):
        """Test: relative directory, absolute filepath, file outside directory"""
        os.chdir(self.test_dir)
        directory = Path(".")
        filepath = Path(self.outside_file).resolve()
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_relative_directory_relative_filepath_inside(self):
        """Test: relative directory, relative filepath, file inside directory"""
        os.chdir(self.test_dir)
        directory = Path(".")
        filepath = Path("test.py")
        # Should not raise
        validate_inside_directory(directory, filepath)

    def test_relative_directory_relative_filepath_outside(self):
        """Test: relative directory, relative filepath, file outside directory"""
        os.chdir(self.outside_dir)
        directory = Path(".")
        # Try to access file in test_dir using relative path
        relative_path = os.path.relpath(self.test_file, self.outside_dir)
        filepath = Path(relative_path)
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_path_traversal_dotdot(self):
        """Test: path traversal attack using .."""
        directory = Path(self.test_dir).resolve()
        # Try to escape using ../
        filepath = Path(self.test_dir) / ".." / ".." / "etc" / "passwd"
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_path_traversal_nested_dotdot(self):
        """Test: path traversal using nested ../"""
        directory = Path(self.nested_dir).resolve()
        # Try to escape to parent directory
        filepath = (
            Path(self.nested_dir) / ".." / ".." / ".." / "etc" / "passwd"
        )
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_symlink_inside_directory(self):
        """Test: symlink pointing to file inside directory"""
        directory = Path(self.test_dir).resolve()
        # Create symlink inside directory pointing to file inside directory
        symlink_path = Path(self.test_dir) / "symlink.py"
        symlink_path.symlink_to(self.test_file)
        # Should not raise
        validate_inside_directory(directory, symlink_path)
        symlink_path.unlink()

    def test_symlink_outside_directory(self):
        """Test: symlink pointing to file outside directory"""
        directory = Path(self.test_dir).resolve()
        # Create symlink inside directory pointing to file outside directory
        symlink_path = Path(self.test_dir) / "symlink.py"
        symlink_path.symlink_to(self.outside_file)
        # Should raise - symlink resolves to outside file
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, symlink_path)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN
        symlink_path.unlink()

    def test_broken_symlink(self):
        """Test: broken symlink"""
        directory = Path(self.test_dir).resolve()
        # Create broken symlink
        broken_symlink = Path(self.test_dir) / "broken.py"
        broken_symlink.symlink_to("nonexistent_file")
        # Broken symlinks can be resolved with resolve(strict=False), but if they
        # point outside the directory, should still fail
        # First test: broken symlink inside directory (should work if resolved path is inside)
        # The symlink itself is inside, so it should pass validation
        # (the actual file doesn't need to exist for validation)
        validate_inside_directory(directory, broken_symlink)

        # Test: broken symlink that resolves outside
        broken_symlink.unlink()
        broken_symlink = Path(self.test_dir) / "broken.py"
        # Create symlink that would resolve outside
        broken_symlink.symlink_to("../../etc/passwd")
        # Should fail because resolved path is outside
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, broken_symlink)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN
        broken_symlink.unlink()

    def test_symlink_to_directory(self):
        """Test: symlink pointing to directory inside"""
        directory = Path(self.test_dir).resolve()
        # Create symlink to nested directory
        symlink_path = Path(self.test_dir) / "nested_link"
        symlink_path.symlink_to(self.nested_dir)
        # Should not raise - symlink resolves to directory inside
        validate_inside_directory(directory, symlink_path)
        symlink_path.unlink()

    def test_nested_file(self):
        """Test: nested file inside directory"""
        directory = Path(self.test_dir).resolve()
        filepath = Path(self.nested_file).resolve()
        # Should not raise
        validate_inside_directory(directory, filepath)

    def test_nonexistent_directory(self):
        """Test: directory doesn't exist"""
        directory = Path(self.test_dir) / "nonexistent"
        filepath = Path(self.test_file).resolve()
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST

    def test_file_as_directory(self):
        """Test: directory path is actually a file"""
        directory = Path(self.test_file).resolve()
        filepath = Path(self.test_file).resolve()
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST

    def test_same_path(self):
        """Test: filepath is the same as directory"""
        directory = Path(self.test_dir).resolve()
        filepath = Path(self.test_dir).resolve()
        # Directory is not inside itself
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_empty_paths(self):
        """Test: empty paths (Path("") resolves to ".")"""
        # Path("") resolves to ".", which is ambiguous
        directory = Path("")
        filepath = Path("")
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST

    def test_absolute_path_with_dotdot_resolved(self):
        """Test: absolute path with .. that resolves inside"""
        directory = Path(self.test_dir).resolve()
        # Create path with .. that still resolves inside
        filepath = Path(self.nested_file).resolve() / ".." / "test.py"
        # Should not raise - resolves to test.py inside directory
        validate_inside_directory(directory, filepath.resolve())

    def test_relative_path_with_dotdot(self):
        """Test: relative path with .. that resolves inside"""
        directory = Path(self.test_dir).resolve()
        # When directory is absolute and filepath is relative, filepath is resolved
        # relative to directory. So "../test.py" from nested_dir would be
        # resolved as (test_dir / "../test.py") which goes outside.
        # Instead, test with a path that stays inside when resolved relative to directory
        nested_rel_path = Path("nested") / ".." / "test.py"
        filepath = nested_rel_path
        # Should not raise - resolves to test.py inside directory
        validate_inside_directory(directory, filepath)

    def test_relative_path_with_dotdot_outside(self):
        """Test: relative path with .. that goes outside"""
        os.chdir(self.nested_dir)
        directory = Path(self.nested_dir).resolve()
        filepath = Path("..") / ".." / ".." / "etc" / "passwd"
        with pytest.raises(HTTPException) as exc_info:
            validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN
