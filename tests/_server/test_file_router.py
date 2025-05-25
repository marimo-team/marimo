from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from marimo._server.file_router import (
    AppFileRouter,
    FileInfo,
    LazyListOfFilesAppFileRouter,
    ListOfFilesAppFileRouter,
    NewFileAppFileRouter,
    flatten_files,
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


def test_flatten_files() -> None:
    """Test flattening a nested directory structure."""
    # Create a nested structure:
    # root/
    #   file1.py
    #   dir1/
    #     file2.py
    #     dir2/
    #       file3.py
    root = FileInfo(
        id="root",
        path="root",
        name="root",
        is_directory=True,
        is_marimo_file=False,
        children=[
            FileInfo(
                id="file1",
                path="root/file1.py",
                name="file1.py",
                is_directory=False,
                is_marimo_file=True,
                children=[],
            ),
            FileInfo(
                id="dir1",
                path="root/dir1",
                name="dir1",
                is_directory=True,
                is_marimo_file=False,
                children=[
                    FileInfo(
                        id="file2",
                        path="root/dir1/file2.py",
                        name="file2.py",
                        is_directory=False,
                        is_marimo_file=True,
                        children=[],
                    ),
                    FileInfo(
                        id="dir2",
                        path="root/dir1/dir2",
                        name="dir2",
                        is_directory=True,
                        is_marimo_file=False,
                        children=[
                            FileInfo(
                                id="file3",
                                path="root/dir1/dir2/file3.py",
                                name="file3.py",
                                is_directory=False,
                                is_marimo_file=True,
                                children=[],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    flattened = flatten_files([root])
    assert len(flattened) == 3
    paths = {f.path for f in flattened}
    assert paths == {
        "root/file1.py",
        "root/dir1/file2.py",
        "root/dir1/dir2/file3.py",
    }
