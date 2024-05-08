from __future__ import annotations

import os
import tempfile
import unittest

from marimo._server.file_router import (
    AppFileRouter,
    LazyListOfFilesAppFileRouter,
    ListOfFilesAppFileRouter,
    NewFileAppFileRouter,
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
        # Write to the temporary files
        self.test_file1.write(file_contents.encode())
        self.test_file1.close()
        self.test_file2.write(file_contents.encode())
        self.test_file2.close()

    def tearDown(self):
        # Clean up temporary files and directory
        os.unlink(self.test_file1.name)
        os.unlink(self.test_file2.name)
        os.rmdir(self.test_dir)

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
            len(files) == 2
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
        assert len(files) == 2

        # Remove the broken symlink
        os.unlink(broken_symlink)

    def test_lazy_list_with_markdown(self):
        # Test the lazy loading of files in a directory with markdown
        router = LazyListOfFilesAppFileRouter(
            self.test_dir, include_markdown=True
        )
        # Create markdown files
        _markdown_file1 = tempfile.NamedTemporaryFile(
            dir=self.test_dir, suffix=".md"
        )
        files = router.files
        assert len(files) == 3

        # Toggling markdown
        router = router.toggle_markdown(False)
        files = router.files
        assert len(files) == 2

        # Toggle markdown back
        router = router.toggle_markdown(True)
        files = router.files
        assert len(files) == 3
