# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from marimo._server.files.path_validator import PathValidator
from marimo._utils.http import HTTPException, HTTPStatus


class TestPathValidator(unittest.TestCase):
    def setUp(self):
        self.temp_root = tempfile.mkdtemp()
        self.test_dir = os.path.join(self.temp_root, "test_directory")
        os.makedirs(self.test_dir)

        self.test_file = os.path.join(self.test_dir, "test.py")
        with open(self.test_file, "w") as f:
            f.write("# test")

        self.outside_dir = os.path.join(self.temp_root, "outside_directory")
        os.makedirs(self.outside_dir)

        self.outside_file = os.path.join(self.outside_dir, "outside.py")
        with open(self.outside_file, "w") as f:
            f.write("# outside")

        self.original_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_root)

    def test_file_inside_directory(self):
        """Test that files inside directory pass validation."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()
        filepath = Path(self.test_file).resolve()
        validator.validate_inside_directory(directory, filepath)

    def test_file_outside_directory(self):
        """Test that files outside directory fail validation."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()
        filepath = Path(self.outside_file).resolve()
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_path_traversal_attack(self):
        """Test that path traversal attacks are prevented."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()
        filepath = Path(self.test_dir) / ".." / ".." / "etc" / "passwd"
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_symlink_inside_directory(self):
        """Test that symlinks pointing inside directory are allowed."""
        validator = PathValidator()
        directory = Path(self.test_dir)
        symlink_path = Path(self.test_dir) / "symlink.py"
        symlink_path.symlink_to(self.test_file)
        validator.validate_inside_directory(directory, symlink_path)
        symlink_path.unlink()

    def test_symlink_to_outside_allowed(self):
        """Test that symlinks pointing outside directory are allowed.

        Since symlinks are preserved (not resolved), the symlink path itself
        is inside the directory, so access is allowed.
        """
        validator = PathValidator()
        directory = Path(self.test_dir)
        symlink_path = Path(self.test_dir) / "symlink.py"
        symlink_path.symlink_to(self.outside_file)
        # Should not raise - symlink path is inside directory
        validator.validate_inside_directory(directory, symlink_path)
        symlink_path.unlink()

    def test_temp_directory_registration(self):
        """Test registering and checking temp directories."""
        validator = PathValidator()
        validator.register_temp_dir(self.outside_dir)

        assert validator.is_file_in_allowed_temp_dir(self.outside_file)
        assert not validator.is_file_in_allowed_temp_dir(self.test_file)

    def test_validate_file_access_with_temp_dir(self):
        """Test that temp directory files bypass validation."""
        validator = PathValidator(base_directory=Path(self.test_dir))
        validator.register_temp_dir(self.outside_dir)
        filepath = Path(self.outside_file)
        # Should not raise - file is in allowed temp dir
        validator.validate_file_access(filepath)

    def test_validate_file_access_outside_base_dir(self):
        """Test that files outside base directory are blocked."""
        validator = PathValidator(base_directory=Path(self.test_dir))
        filepath = Path(self.outside_file)
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_file_access(filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_symlink_directory_outside_allowed(self):
        """Test that files through symlinked directories are allowed.

        Since symlinks are preserved (not resolved), the path through the
        symlink is inside the base directory.
        """
        # Create a symlink to the outside directory inside the test directory
        symlink_path = Path(self.test_dir) / "shared"
        symlink_path.symlink_to(self.outside_dir)

        # Create a file reference through the symlink
        file_through_symlink = symlink_path / "outside.py"

        # Symlinks are preserved (not resolved), so the path
        # /test_dir/shared/outside.py is inside /test_dir/
        validator = PathValidator()
        validator.validate_inside_directory(
            Path(self.test_dir), file_through_symlink
        )  # Should not raise

        symlink_path.unlink()

    def test_absolute_directory_with_relative_filepath(self):
        """Test that relative filepaths are normalized relative to absolute directory."""
        validator = PathValidator()
        # Use absolute directory
        directory = Path(self.test_dir).resolve()
        # Use relative filepath (relative to the directory)
        filepath = Path("test.py")

        # Should validate successfully - test.py is inside test_dir
        validator.validate_inside_directory(directory, filepath)

    def test_absolute_directory_with_relative_filepath_traversal(self):
        """Test path traversal prevention with absolute dir and relative filepath."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()
        # Try to traverse outside using relative path
        filepath = Path("../outside_directory/outside.py")

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_relative_directory_with_relative_filepath(self):
        """Test that both relative paths work correctly from cwd."""
        validator = PathValidator()
        # Change to temp_root so relative paths make sense
        os.chdir(self.temp_root)

        directory = Path("test_directory")
        filepath = Path("test_directory/test.py")

        # Should validate successfully
        validator.validate_inside_directory(directory, filepath)

    def test_relative_directory_with_relative_filepath_outside(self):
        """Test that relative filepath outside relative directory fails."""
        validator = PathValidator()
        os.chdir(self.temp_root)

        directory = Path("test_directory")
        # File is outside the test_directory
        filepath = Path("outside_directory/outside.py")

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_absolute_directory_with_nested_relative_filepath(self):
        """Test nested relative filepath with absolute directory."""
        validator = PathValidator()
        # Create a nested directory structure
        nested_dir = os.path.join(self.test_dir, "nested", "deeper")
        os.makedirs(nested_dir)
        nested_file = os.path.join(nested_dir, "nested.py")
        with open(nested_file, "w") as f:
            f.write("# nested")

        directory = Path(self.test_dir).resolve()
        # Relative path to nested file
        filepath = Path("nested/deeper/nested.py")

        # Should validate successfully
        validator.validate_inside_directory(directory, filepath)

    def test_absolute_directory_with_dot_relative_filepath(self):
        """Test that ./ prefix in relative filepath works correctly."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()
        # Relative path with ./ prefix
        filepath = Path("./test.py")

        # Should validate successfully
        validator.validate_inside_directory(directory, filepath)

    def test_relative_directory_with_absolute_filepath_inside(self):
        """Test relative directory with absolute filepath inside it."""
        validator = PathValidator()
        os.chdir(self.temp_root)

        directory = Path("test_directory")
        # Absolute path to file inside the relative directory
        filepath = Path(self.test_file).resolve()

        # Should validate successfully
        validator.validate_inside_directory(directory, filepath)

    def test_relative_directory_with_absolute_filepath_outside(self):
        """Test relative directory with absolute filepath outside it."""
        validator = PathValidator()
        os.chdir(self.temp_root)

        directory = Path("test_directory")
        # Absolute path to file outside the directory
        filepath = Path(self.outside_file).resolve()

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_path_traversal_staying_inside(self):
        """Test path traversal that goes up but stays inside directory."""
        validator = PathValidator()
        # Create nested structure: test_dir/subdir/file.py
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir)

        directory = Path(self.test_dir).resolve()
        # Path goes up from subdir but stays in test_dir
        filepath = Path("subdir/../test.py")

        # Should validate successfully - normalized path is test_dir/test.py
        validator.validate_inside_directory(directory, filepath)

    def test_path_traversal_middle_of_path(self):
        """Test path traversal in the middle of a path."""
        validator = PathValidator()
        # Create structure: test_dir/dir1/dir2/file.py
        dir1 = os.path.join(self.test_dir, "dir1")
        dir2 = os.path.join(self.test_dir, "dir2")
        os.makedirs(dir1)
        os.makedirs(dir2)
        file_in_dir2 = os.path.join(dir2, "file.py")
        with open(file_in_dir2, "w") as f:
            f.write("# file")

        directory = Path(self.test_dir).resolve()
        # Path has traversal in the middle: dir1/../dir2/file.py
        filepath = Path("dir1/../dir2/file.py")

        # Should validate successfully
        validator.validate_inside_directory(directory, filepath)

    def test_multiple_level_path_traversal(self):
        """Test multiple levels of path traversal to escape."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()
        # Try to go up multiple levels
        filepath = Path("../../../../../../etc/passwd")

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN

    def test_filepath_equals_directory(self):
        """Test that filepath cannot be the same as directory."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()
        filepath = directory

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN
        assert "same as directory" in str(exc_info.value.detail)

    def test_nonexistent_directory(self):
        """Test that validation fails for non-existent directory."""
        validator = PathValidator()
        nonexistent_dir = Path(self.temp_root) / "does_not_exist"
        filepath = Path("test.py")

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(nonexistent_dir, filepath)
        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "does not exist" in str(exc_info.value.detail)

    def test_directory_is_file(self):
        """Test that validation fails when directory is actually a file."""
        validator = PathValidator()
        # Use test_file as directory (it's actually a file)
        not_a_directory = Path(self.test_file)
        filepath = Path("test.py")

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(not_a_directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "not a directory" in str(exc_info.value.detail)

    def test_empty_paths(self):
        """Test that empty/ambiguous paths are rejected."""
        validator = PathValidator()
        # Path("") resolves to Path(".")
        directory = Path(".")
        filepath = Path(".")

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_inside_directory(directory, filepath)
        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Empty or ambiguous" in str(exc_info.value.detail)

    def test_broken_symlink_filepath(self):
        """Test handling of broken symlinks in filepath."""
        validator = PathValidator()
        directory = Path(self.test_dir)
        # Create a symlink to a non-existent file
        broken_symlink = Path(self.test_dir) / "broken_link.py"
        broken_symlink.symlink_to("/nonexistent/path/file.py")

        # The symlink path itself is inside the directory, so it should be allowed
        # (symlinks are not resolved)
        validator.validate_inside_directory(directory, broken_symlink)

        broken_symlink.unlink()

    def test_symlink_directory(self):
        """Test validation when the directory itself is a symlink."""
        validator = PathValidator()
        # Create a symlink to test_dir
        symlink_dir = Path(self.temp_root) / "symlink_to_test_dir"
        symlink_dir.symlink_to(self.test_dir)

        # Use the symlink as the directory
        filepath = symlink_dir / "test.py"

        # Should validate successfully
        validator.validate_inside_directory(symlink_dir, filepath)

        symlink_dir.unlink()

    def test_redundant_path_components(self):
        """Test paths with redundant components like ./ and //."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()

        # Test various redundant path formats
        test_cases = [
            Path("./././test.py"),  # Multiple ./
            Path("test.py"),  # Normal case for comparison
        ]

        for filepath in test_cases:
            # All should validate successfully
            validator.validate_inside_directory(directory, filepath)

    def test_trailing_slash_in_filepath(self):
        """Test filepath with trailing slash."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()
        # Create a subdirectory
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        # Path with trailing slash (refers to directory)
        filepath = Path("subdir/")

        # Should validate successfully - subdir is inside test_dir
        validator.validate_inside_directory(directory, filepath)

    def test_absolute_filepath_with_traversal(self):
        """Test absolute filepath with traversal components."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()

        # Create an absolute path with .. in it
        # E.g., /path/to/test_dir/subdir/../test.py
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        # Use resolved directory to ensure consistent path representation
        filepath = directory / "subdir" / ".." / "test.py"

        # Should validate successfully after normalization
        validator.validate_inside_directory(directory, filepath)

    def test_case_sensitive_paths(self):
        """Test that path validation is case-sensitive on case-sensitive filesystems."""
        validator = PathValidator()
        directory = Path(self.test_dir).resolve()

        # Create a file with specific casing
        case_file = os.path.join(self.test_dir, "CamelCase.py")
        with open(case_file, "w") as f:
            f.write("# test")

        # Use the exact casing
        filepath = Path("CamelCase.py")

        # Should validate successfully
        validator.validate_inside_directory(directory, filepath)
