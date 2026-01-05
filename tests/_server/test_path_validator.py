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
