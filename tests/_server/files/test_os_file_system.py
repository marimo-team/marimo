from __future__ import annotations

import os
from tempfile import TemporaryDirectory

import pytest

from marimo._server.files.os_file_system import OSFileSystem, natural_sort
from marimo._server.models.files import FileDetailsResponse


@pytest.fixture
def test_dir():
    # Create a temporary directory for the tests
    temp_dir = TemporaryDirectory()
    test_dir = temp_dir.name
    yield test_dir
    # Cleanup the temporary directory after each test
    temp_dir.cleanup()


@pytest.fixture
def fs():
    return OSFileSystem()


def test_create_file(test_dir: str, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    fs.create_file_or_directory(test_dir, "file", test_file_name, None)
    expected_path = os.path.join(test_dir, test_file_name)
    assert os.path.exists(expected_path)


def test_create_file_with_duplicate_name(
    test_dir: str, fs: OSFileSystem
) -> None:
    test_file_name = "test_file.txt"
    fs.create_file_or_directory(test_dir, "file", test_file_name, None)
    # Create a file with the same name
    fs.create_file_or_directory(test_dir, "file", test_file_name, None)
    # Expecting a new file with a different name
    expected_path = os.path.join(test_dir, "test_file_1.txt")
    assert os.path.exists(expected_path)


def test_create_file_and_parent_directories(
    test_dir: str, fs: OSFileSystem
) -> None:
    test_file_name = "test_file.txt"
    fs.create_file_or_directory(
        f"{test_dir}/parent", "file", test_file_name, None
    )
    expected_path = os.path.join(test_dir, "parent", test_file_name)
    assert os.path.exists(expected_path)


def test_create_directory(test_dir: str, fs: OSFileSystem) -> None:
    test_dir_name = "test_dir"
    fs.create_file_or_directory(test_dir, "directory", test_dir_name, None)
    expected_path = os.path.join(test_dir, test_dir_name)
    assert os.path.isdir(expected_path)


def test_create_with_empty_name(test_dir: str, fs: OSFileSystem) -> None:
    with pytest.raises(ValueError):
        fs.create_file_or_directory(test_dir, "file", "", None)


def test_create_with_disallowed_name(test_dir: str, fs: OSFileSystem) -> None:
    with pytest.raises(ValueError):
        fs.create_file_or_directory(test_dir, "file", ".", None)


def test_list_files(test_dir: str, fs: OSFileSystem) -> None:
    # Create a test file and directory
    test_create_file(test_dir, fs)
    test_create_directory(test_dir, fs)
    files = fs.list_files(test_dir)
    assert len(files) == 2  # Expecting 1 file and 1 directory


def test_list_files_with_broken_directory_symlink(
    test_dir: str, fs: OSFileSystem
) -> None:
    # Create a broken symlink
    broken_symlink = os.path.join(test_dir, "broken_symlink")
    os.symlink("non_existent_file", broken_symlink)
    files = fs.list_files(test_dir)
    assert len(files) == 0


def test_get_details(test_dir: str, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    fs.create_file_or_directory(
        test_dir,
        "file",
        test_file_name,
        b"some content",
    )
    file_info = fs.get_details(os.path.join(test_dir, test_file_name))
    assert isinstance(file_info, FileDetailsResponse)
    assert file_info.file.name == test_file_name
    assert file_info.mime_type == "text/plain"
    assert file_info.contents == "some content"


@pytest.mark.parametrize("encoding", ["utf-8", "iso-8859-1"])
def test_get_details_marimo_file(
    test_dir: str, fs: OSFileSystem, encoding
) -> None:
    test_file_name = "app.py"
    content = """
        import marimo
        app = marimo.App()

        @app.cell
        def __():
            import marimo as mo
            return mo,

        if __name__ == "__main__":
            # mäin
            app.run()
        """
    fs.create_file_or_directory(
        test_dir, "file", test_file_name, content.encode(encoding=encoding)
    )
    file_path = os.path.join(test_dir, test_file_name)
    file_info = fs.get_details(file_path)
    assert isinstance(file_info, FileDetailsResponse)
    assert file_info.file.is_marimo_file


def test_open_file(test_dir: str, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    test_content = "Hello, World!"
    with open(os.path.join(test_dir, test_file_name), "w") as f:
        f.write(test_content)
    content = fs.open_file(os.path.join(test_dir, test_file_name))
    assert content == test_content


def test_delete_file(test_dir: str, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    file_path = os.path.join(test_dir, test_file_name)
    with open(file_path, "w"):
        pass
    fs.delete_file_or_directory(file_path)
    assert not os.path.exists(file_path)


def test_move_file(test_dir: str, fs: OSFileSystem) -> None:
    original_file_name = "original.txt"
    new_file_name = "new.txt"
    original_path = os.path.join(test_dir, original_file_name)
    new_path = os.path.join(test_dir, new_file_name)
    with open(original_path, "w") as f:
        f.write("Test")
    fs.move_file_or_directory(original_path, new_path)
    assert os.path.exists(new_path)
    assert not os.path.exists(original_path)


def test_move_with_disallowed_name(test_dir: str, fs: OSFileSystem) -> None:
    original_file_name = "original.txt"
    new_file_name = "."
    original_path = os.path.join(test_dir, original_file_name)
    new_path = os.path.join(test_dir, new_file_name)
    with open(original_path, "w"):
        pass
    with pytest.raises(ValueError):
        fs.move_file_or_directory(original_path, new_path)


def test_update_file(test_dir: str, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    file_path = os.path.join(test_dir, test_file_name)
    with open(file_path, "w") as f:
        f.write("Initial content")
    new_content = "Updated content"
    fs.update_file(file_path, new_content)
    with open(file_path) as f:
        assert f.read() == new_content


def test_natural_sort_key() -> None:
    filenames = [
        "file1.txt",
        "file10.txt",
        "file2.txt",
        "file20.txt",
        "1.txt",
        "10.txt",
        "2.txt",
        "20.txt",
    ]
    sorted_files = sorted(filenames, key=natural_sort)
    expected_order = [
        "1.txt",
        "2.txt",
        "10.txt",
        "20.txt",
        "file1.txt",
        "file2.txt",
        "file10.txt",
        "file20.txt",
    ]
    assert sorted_files == expected_order
