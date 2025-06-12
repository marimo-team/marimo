from __future__ import annotations

from pathlib import Path

import pytest

from marimo._server.files.os_file_system import OSFileSystem, natural_sort
from marimo._server.models.files import FileDetailsResponse


@pytest.fixture
def test_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    temp_dir = tmp_path_factory.mktemp("marimo_test")
    # pytest handles cleanup
    return temp_dir


@pytest.fixture
def fs():
    return OSFileSystem()


def test_create_file(test_dir: Path, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    fs.create_file_or_directory(str(test_dir), "file", test_file_name, None)
    expected_path = test_dir / test_file_name
    assert expected_path.exists()


def test_create_file_with_duplicate_name(
    test_dir: Path, fs: OSFileSystem
) -> None:
    test_file_name = "test_file.txt"
    fs.create_file_or_directory(str(test_dir), "file", test_file_name, None)
    fs.create_file_or_directory(str(test_dir), "file", test_file_name, None)
    expected_path = test_dir / "test_file_1.txt"
    assert expected_path.exists()


def test_create_file_and_parent_directories(
    test_dir: Path, fs: OSFileSystem
) -> None:
    test_file_name = "test_file.txt"
    fs.create_file_or_directory(
        str(test_dir / "parent"), "file", test_file_name, None
    )
    expected_path = test_dir / "parent" / test_file_name
    assert expected_path.exists()


def test_create_directory(test_dir: Path, fs: OSFileSystem) -> None:
    test_dir_name = "test_dir"
    fs.create_file_or_directory(
        str(test_dir), "directory", test_dir_name, None
    )
    expected_path = test_dir / test_dir_name
    assert expected_path.is_dir()


def test_create_with_empty_name(test_dir: Path, fs: OSFileSystem) -> None:
    with pytest.raises(ValueError):
        fs.create_file_or_directory(str(test_dir), "file", "", None)


def test_create_with_disallowed_name(test_dir: Path, fs: OSFileSystem) -> None:
    with pytest.raises(ValueError):
        fs.create_file_or_directory(str(test_dir), "file", ".", None)


def test_list_files(test_dir: Path, fs: OSFileSystem) -> None:
    test_create_file(test_dir, fs)
    test_create_directory(test_dir, fs)
    files = fs.list_files(str(test_dir))
    assert len(files) == 2  # Expecting 1 file and 1 directory


def test_list_files_with_broken_directory_symlink(
    test_dir: Path, fs: OSFileSystem
) -> None:
    broken_symlink = test_dir / "broken_symlink"
    broken_symlink.symlink_to("non_existent_file")
    files = fs.list_files(str(test_dir))
    assert len(files) == 0


def test_get_details(test_dir: Path, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    fs.create_file_or_directory(
        str(test_dir),
        "file",
        test_file_name,
        b"some content",
    )
    file_path = test_dir / test_file_name
    file_info = fs.get_details(str(file_path))
    assert isinstance(file_info, FileDetailsResponse)
    assert file_info.file.name == test_file_name
    assert file_info.mime_type == "text/plain"
    assert file_info.contents == "some content"
    file_info2 = fs.get_details(str(file_path), contents="direct content")
    assert file_info2.contents == "direct content"


@pytest.mark.parametrize("encoding", ["utf-8", "iso-8859-1"])
def test_get_details_marimo_file(
    test_dir: Path, fs: OSFileSystem, encoding: str
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
        str(test_dir),
        "file",
        test_file_name,
        content.encode(encoding=encoding),
    )
    file_path = test_dir / test_file_name
    file_info = fs.get_details(str(file_path))
    assert isinstance(file_info, FileDetailsResponse)
    assert file_info.file.is_marimo_file


def test_open_file(test_dir: Path, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    test_content = "Hello, World!"
    file_path = test_dir / test_file_name
    file_path.write_text(test_content)
    content = fs.open_file(str(file_path))
    assert content == test_content


def test_delete_file(test_dir: Path, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    file_path = test_dir / test_file_name
    file_path.write_text("")
    fs.delete_file_or_directory(str(file_path))
    assert not file_path.exists()


def test_move_file(test_dir: Path, fs: OSFileSystem) -> None:
    original_file_name = "original.txt"
    new_file_name = "new.txt"
    original_path = test_dir / original_file_name
    new_path = test_dir / new_file_name
    original_path.write_text("Test")
    fs.move_file_or_directory(str(original_path), str(new_path))
    assert new_path.exists()
    assert not original_path.exists()


def test_move_with_disallowed_name(test_dir: Path, fs: OSFileSystem) -> None:
    original_file_name = "original.txt"
    new_file_name = "."
    original_path = test_dir / original_file_name
    new_path = test_dir / new_file_name
    original_path.write_text("")
    with pytest.raises(ValueError):
        fs.move_file_or_directory(str(original_path), str(new_path))


def test_update_file(test_dir: Path, fs: OSFileSystem) -> None:
    test_file_name = "test_file.txt"
    file_path = test_dir / test_file_name
    file_path.write_text("Initial content")
    new_content = "Updated content"
    fs.update_file(str(file_path), new_content)
    assert file_path.read_text() == new_content


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


def test_get_details_with_encoding_and_contents(
    test_dir: Path, fs: OSFileSystem
) -> None:
    test_file_name = "test_file.txt"
    file_path = test_dir / test_file_name
    file_path.write_text("should not see this", encoding="utf-8")
    result = fs.get_details(
        str(file_path), encoding="utf-8", contents="override"
    )
    assert result.contents == "override"


def test_get_details_directory(test_dir: Path, fs: OSFileSystem) -> None:
    dir_path = test_dir / "subdir"
    dir_path.mkdir()
    result = fs.get_details(str(dir_path))
    assert result.file.is_directory
    assert result.contents is None


def test_get_details_nonexistent_file(fs: OSFileSystem) -> None:
    from tempfile import gettempdir

    non_existent = Path(gettempdir()) / "this_file_does_not_exist.txt"
    with pytest.raises(FileNotFoundError):
        fs.get_details(str(non_existent))


def test_get_details_binary_file(test_dir: Path, fs: OSFileSystem) -> None:
    file_path = test_dir / "binfile.bin"
    file_path.write_bytes(b"\x00\x01\x02\x03")
    result = fs.get_details(str(file_path))

    assert result.contents == "\x00\x01\x02\x03"


def test_get_details_empty_string_contents(
    test_dir: Path, fs: OSFileSystem
) -> None:
    test_file_name = "test_file.txt"
    file_path = test_dir / test_file_name
    file_path.write_text("should not see this", encoding="utf-8")
    result = fs.get_details(str(file_path), contents="")
    assert result.contents == ""


def test_get_details_none_contents_reads_disk(
    test_dir: Path, fs: OSFileSystem
) -> None:
    test_file_name = "test_file.txt"
    file_path = test_dir / test_file_name
    file_path.write_text("disk content", encoding="utf-8")
    result = fs.get_details(str(file_path), contents=None)
    assert result.contents == "disk content"


def test_get_details_contents_for_directory(
    test_dir: Path, fs: OSFileSystem
) -> None:
    dir_path = test_dir / "subdir"
    dir_path.mkdir()
    result = fs.get_details(str(dir_path), contents="should be ignored")
    assert result.file.is_directory
    assert result.contents is None


def test_get_details_non_utf8_encoding_and_contents(
    test_dir: Path, fs: OSFileSystem
) -> None:
    test_file_name = "latin1.txt"
    file_path = test_dir / test_file_name
    content = "caf\xe9".encode("latin-1")
    file_path.write_bytes(content)
    result = fs.get_details(str(file_path), encoding="latin-1")
    assert result.contents == "café"
    base64_content = __import__("base64").b64encode(content).decode("utf-8")
    result_utf8 = fs.get_details(str(file_path), encoding="utf-8")
    assert result_utf8.contents == base64_content
    result2 = fs.get_details(
        str(file_path), encoding="utf-8", contents="override"
    )
    assert result2.contents == "override"
