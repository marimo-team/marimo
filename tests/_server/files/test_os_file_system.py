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
        self.fs.create_file_or_directory(self.test_dir, "file", test_file_name)
        expected_path = os.path.join(self.test_dir, test_file_name)
        assert os.path.exists(expected_path)

    def test_create_directory(self):
        test_dir_name = "test_dir"
        self.fs.create_file_or_directory(
            self.test_dir, "directory", test_dir_name
        )
        expected_path = os.path.join(self.test_dir, test_dir_name)
        assert os.path.isdir(expected_path)

    def test_list_files(self):
        # Create a test file and directory
        self.test_create_file()
        self.test_create_directory()
        files = self.fs.list_files(self.test_dir)
        assert len(files) == 2  # Expecting 1 file and 1 directory

    def test_get_details(self):
        test_file_name = "test_file.txt"
        self.fs.create_file_or_directory(self.test_dir, "file", test_file_name)
        file_info = self.fs.get_details(
            os.path.join(self.test_dir, test_file_name)
        )
        assert isinstance(file_info, FileDetailsResponse)
        assert file_info.file.name == test_file_name
        assert file_info.mime_type == "text/plain"

    def test_get_details_marimo_file(self):
        test_file_name = "app.py"
        self.fs.create_file_or_directory(self.test_dir, "file", test_file_name)
        file_path = os.path.join(self.test_dir, test_file_name)
        with open(file_path, "w") as f:
            f.write(
                """
            import marimo
            app = marimo.App()

            @app.cell
            def __():
                import marimo as mo
                return mo,

            if __name__ == "__main__":
                app.run()
            """
            )
            f.close()
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

    def test_update_file(self):
        original_file_name = "original.txt"
        new_file_name = "new.txt"
        original_path = os.path.join(self.test_dir, original_file_name)
        new_path = os.path.join(self.test_dir, new_file_name)
        with open(original_path, "w") as f:
            f.write("Test")
        self.fs.update_file_or_directory(original_path, new_path)
        assert os.path.exists(new_path)
        assert not os.path.exists(original_path)
