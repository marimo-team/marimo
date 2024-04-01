import os
import unittest
from tempfile import TemporaryDirectory

from marimo._server.files.os_file_system import OSFileSystem
from marimo._server.models.files import FileDetailsResponse


class TestOSFileSystem(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the tests
        self.temp_dir = TemporaryDirectory()
        self.test_dir = self.temp_dir.name
        self.fs = OSFileSystem()

    def tearDown(self):
        # Cleanup the temporary directory after each test
        self.temp_dir.cleanup()

    def test_create_file(self):
        test_file_name = "test_file.txt"
        self.fs.create_file_or_directory(
            self.test_dir, "file", test_file_name, None
        )
        expected_path = os.path.join(self.test_dir, test_file_name)
        assert os.path.exists(expected_path)

    def test_create_file_with_duplicate_name(self):
        test_file_name = "test_file.txt"
        self.fs.create_file_or_directory(
            self.test_dir, "file", test_file_name, None
        )
        # Create a file with the same name
        self.fs.create_file_or_directory(
            self.test_dir, "file", test_file_name, None
        )
        # Expecting a new file with a different name
        expected_path = os.path.join(self.test_dir, "test_file_1.txt")
        assert os.path.exists(expected_path)

    def test_create_directory(self):
        test_dir_name = "test_dir"
        self.fs.create_file_or_directory(
            self.test_dir, "directory", test_dir_name, None
        )
        expected_path = os.path.join(self.test_dir, test_dir_name)
        assert os.path.isdir(expected_path)

    def test_create_with_empty_name(self):
        with self.assertRaises(ValueError):
            self.fs.create_file_or_directory(self.test_dir, "file", "", None)

    def test_create_with_disallowed_name(self):
        with self.assertRaises(ValueError):
            self.fs.create_file_or_directory(self.test_dir, "file", ".", None)

    def test_list_files(self):
        # Create a test file and directory
        self.test_create_file()
        self.test_create_directory()
        files = self.fs.list_files(self.test_dir)
        assert len(files) == 2  # Expecting 1 file and 1 directory

    def test_list_files_with_broken_directory_symlink(self):
        # Create a broken symlink
        broken_symlink = os.path.join(self.test_dir, "broken_symlink")
        os.symlink("non_existent_file", broken_symlink)
        files = self.fs.list_files(self.test_dir)
        assert len(files) == 0

    def test_get_details(self):
        test_file_name = "test_file.txt"
        self.fs.create_file_or_directory(
            self.test_dir,
            "file",
            test_file_name,
            "some content".encode("utf-8"),
        )
        file_info = self.fs.get_details(
            os.path.join(self.test_dir, test_file_name)
        )
        assert isinstance(file_info, FileDetailsResponse)
        assert file_info.file.name == test_file_name
        assert file_info.mime_type == "text/plain"
        assert file_info.contents == "some content"

    def test_get_details_marimo_file(self):
        test_file_name = "app.py"
        content = """
            import marimo
            app = marimo.App()

            @app.cell
            def __():
                import marimo as mo
                return mo,

            if __name__ == "__main__":
                app.run()
            """
        self.fs.create_file_or_directory(
            self.test_dir, "file", test_file_name, content.encode("utf-8")
        )
        file_path = os.path.join(self.test_dir, test_file_name)
        file_info = self.fs.get_details(file_path)
        assert isinstance(file_info, FileDetailsResponse)
        assert file_info.file.is_marimo_file

    def test_open_file(self):
        test_file_name = "test_file.txt"
        test_content = "Hello, World!"
        with open(os.path.join(self.test_dir, test_file_name), "w") as f:
            f.write(test_content)
        content = self.fs.open_file(
            os.path.join(self.test_dir, test_file_name)
        )
        assert content == test_content

    def test_delete_file(self):
        test_file_name = "test_file.txt"
        file_path = os.path.join(self.test_dir, test_file_name)
        with open(file_path, "w"):
            pass
        self.fs.delete_file_or_directory(file_path)
        assert not os.path.exists(file_path)

    def test_move_file(self):
        original_file_name = "original.txt"
        new_file_name = "new.txt"
        original_path = os.path.join(self.test_dir, original_file_name)
        new_path = os.path.join(self.test_dir, new_file_name)
        with open(original_path, "w") as f:
            f.write("Test")
        self.fs.move_file_or_directory(original_path, new_path)
        assert os.path.exists(new_path)
        assert not os.path.exists(original_path)

    def test_move_with_disallowed_name(self):
        original_file_name = "original.txt"
        new_file_name = "."
        original_path = os.path.join(self.test_dir, original_file_name)
        new_path = os.path.join(self.test_dir, new_file_name)
        with open(original_path, "w"):
            pass
        with self.assertRaises(ValueError):
            self.fs.move_file_or_directory(original_path, new_path)

    def test_update_file(self):
        test_file_name = "test_file.txt"
        file_path = os.path.join(self.test_dir, test_file_name)
        with open(file_path, "w") as f:
            f.write("Initial content")
        new_content = "Updated content"
        self.fs.update_file(file_path, new_content)
        with open(file_path, "r") as f:
            assert f.read() == new_content
