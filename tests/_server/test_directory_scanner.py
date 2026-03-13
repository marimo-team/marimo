# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from marimo._server.files.directory_scanner import (
    DirectoryScanner,
    is_marimo_app,
)


def test_python_app_detected():
    """Test that Python marimo apps are detected."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write("import marimo\napp = marimo.App()\n")
        f.flush()
        assert is_marimo_app(f.name)
    os.unlink(f.name)


def test_python_non_app():
    """Test that non-marimo Python files return False."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write("import sys\nprint('hello')\n")
        f.flush()
        assert not is_marimo_app(f.name)
    os.unlink(f.name)


def test_markdown_app_detected():
    """Test that markdown files with marimo-version are detected."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False
    ) as f:
        f.write("---\nmarimo-version: 0.1.0\n---\n")
        f.flush()
        assert is_marimo_app(f.name)
    os.unlink(f.name)


class TestDirectoryScanner(unittest.TestCase):
    def setUp(self):
        self.temp_root = tempfile.mkdtemp()
        self.test_dir = os.path.join(self.temp_root, "test_directory")
        os.makedirs(self.test_dir)

        # Create marimo files
        with open(os.path.join(self.test_dir, "app1.py"), "w") as f:
            f.write("import marimo\napp = marimo.App()\n")
        with open(os.path.join(self.test_dir, "app2.py"), "w") as f:
            f.write("import marimo\napp = marimo.App()\n")

        # Create markdown file
        with open(os.path.join(self.test_dir, "notebook.md"), "w") as f:
            f.write("---\nmarimo-version: 0.1.0\n---\n")

        # Create nested directory with marimo file
        self.nested_dir = os.path.join(self.test_dir, "nested")
        os.makedirs(self.nested_dir)
        with open(os.path.join(self.nested_dir, "nested_app.py"), "w") as f:
            f.write("import marimo\napp = marimo.App()\n")

    def tearDown(self):
        shutil.rmtree(self.temp_root)

    def test_basic_scan(self):
        """Test basic directory scanning."""
        scanner = DirectoryScanner(self.test_dir)
        files = scanner.scan()
        file_names = [f.name for f in files if not f.is_directory]
        assert len(file_names) == 2
        assert "app1.py" in file_names
        assert "app2.py" in file_names

    def test_scan_with_markdown(self):
        """Test scanning with markdown files included."""
        scanner = DirectoryScanner(self.test_dir, include_markdown=True)
        files = scanner.scan()
        file_names = [f.name for f in files if not f.is_directory]
        assert len(file_names) == 3
        assert "notebook.md" in file_names

    def test_scan_nested_directories(self):
        """Test scanning nested directories."""
        scanner = DirectoryScanner(self.test_dir)
        files = scanner.scan()
        nested_dirs = [
            f for f in files if f.is_directory and f.name == "nested"
        ]
        assert len(nested_dirs) == 1
        assert nested_dirs[0].children is not None
        assert nested_dirs[0].children[0].name == "nested_app.py"

    def test_max_files_limit(self):
        """Test that max_files limit is enforced."""
        for i in range(10):
            with open(os.path.join(self.test_dir, f"app{i + 3}.py"), "w") as f:
                f.write("import marimo\napp = marimo.App()\n")

        scanner = DirectoryScanner(self.test_dir, max_files=5)
        files = scanner.scan()

        def count_files(file_list: list) -> int:
            total = 0
            for f in file_list:
                if f.is_directory:
                    if f.children:
                        total += count_files(f.children)
                else:
                    total += 1
            return total

        assert count_files(files) == 5

    def test_skip_common_directories(self):
        """Test that common directories are skipped."""
        for dirname in ["venv", "node_modules", "__pycache__", ".git"]:
            skip_dir = os.path.join(self.test_dir, dirname)
            os.makedirs(skip_dir)
            with open(os.path.join(skip_dir, "app.py"), "w") as f:
                f.write("import marimo\napp = marimo.App()\n")

        scanner = DirectoryScanner(self.test_dir)
        files = scanner.scan()
        file_paths = [f.path for f in files if not f.is_directory]
        for path in file_paths:
            assert "venv" not in path
            assert "node_modules" not in path

    def test_skip_hidden_files(self):
        """Test that hidden files are skipped."""
        with open(os.path.join(self.test_dir, ".hidden_app.py"), "w") as f:
            f.write("import marimo\napp = marimo.App()\n")

        scanner = DirectoryScanner(self.test_dir)
        files = scanner.scan()
        file_names = [f.name for f in files if not f.is_directory]
        assert ".hidden_app.py" not in file_names

    def test_partial_results_populated_during_scan(self):
        """Test that partial_results is populated during scanning."""
        scanner = DirectoryScanner(self.test_dir)
        # partial_results starts empty
        assert scanner.partial_results == []
        files = scanner.scan()
        # After scan, partial_results contains all found files (flat list)
        assert len(scanner.partial_results) >= 2
        # All items in partial_results should be non-directory files
        for f in scanner.partial_results:
            assert not f.is_directory
            assert f.is_marimo_file
