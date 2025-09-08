from __future__ import annotations

from pathlib import Path

import pytest

from marimo._server.files.os_file_system import OSFileSystem
from marimo._server.models.files import FileDetailsResponse
from marimo._utils.files import natural_sort


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


def test_search_basic(test_dir: Path, fs: OSFileSystem) -> None:
    """Test basic search functionality."""
    # Create test files
    (test_dir / "hello.txt").write_text("content")
    (test_dir / "world.txt").write_text("content")
    (test_dir / "hello_world.py").write_text("print('hello')")

    # Search for "hello"
    results = fs.search(query="hello", path=str(test_dir))

    # Should find hello.txt and hello_world.py
    assert len(results) >= 2
    file_names = {f.name for f in results}
    assert "hello.txt" in file_names
    assert "hello_world.py" in file_names
    assert "world.txt" not in file_names


def test_search_empty_query(test_dir: Path, fs: OSFileSystem) -> None:
    """Test search with empty query returns no results."""
    (test_dir / "test.txt").write_text("content")

    results = fs.search(query="", path=str(test_dir))
    assert results == []

    results = fs.search(query="   ", path=str(test_dir))
    assert results == []


def test_search_case_insensitive(test_dir: Path, fs: OSFileSystem) -> None:
    """Test search is case insensitive."""
    # Create files with mixed case
    (test_dir / "CamelCase.txt").write_text("content")
    (test_dir / "lowercase.txt").write_text("content")
    (test_dir / "UPPERCASE.txt").write_text("content")

    results = fs.search(query="case", path=str(test_dir))

    file_names = {f.name for f in results}
    assert "CamelCase.txt" in file_names
    assert "lowercase.txt" in file_names
    assert "UPPERCASE.txt" in file_names


def test_search_with_depth_limit(test_dir: Path, fs: OSFileSystem) -> None:
    """Test search respects depth limit."""
    # Create files at different depths
    (test_dir / "root_match.txt").write_text("content")

    # Level 1
    level1 = test_dir / "level1"
    level1.mkdir()
    (level1 / "level1_match.txt").write_text("content")

    # Level 2
    level2 = level1 / "level2"
    level2.mkdir()
    (level2 / "level2_match.txt").write_text("content")

    # Level 3
    level3 = level2 / "level3"
    level3.mkdir()
    (level3 / "level3_match.txt").write_text("content")

    # Search with depth=1 - should find root and level1 files only
    results = fs.search(query="match", path=str(test_dir), depth=1)
    file_names = {f.name for f in results}
    assert "root_match.txt" in file_names
    assert "level1_match.txt" in file_names
    assert "level2_match.txt" not in file_names
    assert "level3_match.txt" not in file_names

    # Search with depth=2 - should find up to level2
    results = fs.search(query="match", path=str(test_dir), depth=2)
    file_names = {f.name for f in results}
    assert "root_match.txt" in file_names
    assert "level1_match.txt" in file_names
    assert "level2_match.txt" in file_names
    assert "level3_match.txt" not in file_names


def test_search_with_limit(test_dir: Path, fs: OSFileSystem) -> None:
    """Test search respects result limit."""
    # Create many matching files
    for i in range(10):
        (test_dir / f"test_{i}.txt").write_text("content")

    # Search with limit=3
    results = fs.search(query="test", path=str(test_dir), limit=3)
    assert len(results) <= 3

    # Search with limit=5
    results = fs.search(query="test", path=str(test_dir), limit=5)
    assert len(results) <= 5


def test_search_result_ordering(test_dir: Path, fs: OSFileSystem) -> None:
    """Test search results are ordered by relevance."""
    # Create files with different match types
    (test_dir / "test").mkdir()  # exact match (directory)
    (test_dir / "test.txt").write_text("content")  # exact match (file)
    (test_dir / "test_file.py").write_text("content")  # starts with
    (test_dir / "my_test.txt").write_text("content")  # contains
    (test_dir / "another_test_file.py").write_text("content")  # contains

    results = fs.search(query="test", path=str(test_dir))

    # Results should be ordered by relevance
    file_names = [f.name for f in results]

    # Exact matches should come first
    exact_matches = [
        name for name in file_names if name == "test" or name == "test.txt"
    ]
    assert len(exact_matches) >= 1

    # "test.txt" should come before "my_test.txt"
    test_txt_idx = file_names.index("test.txt")
    my_test_idx = file_names.index("my_test.txt")
    assert test_txt_idx < my_test_idx


def test_search_includes_directories(test_dir: Path, fs: OSFileSystem) -> None:
    """Test search includes both files and directories."""
    # Create matching directory and file
    (test_dir / "testdir").mkdir()
    (test_dir / "testfile.txt").write_text("content")

    results = fs.search(query="test", path=str(test_dir))

    has_directory = any(f.is_directory for f in results)
    has_file = any(not f.is_directory for f in results)
    assert has_directory
    assert has_file


def test_search_respects_ignore_list(test_dir: Path, fs: OSFileSystem) -> None:
    """Test search respects the ignore list."""
    # Create files that should be ignored
    (test_dir / ".DS_Store").write_text("content")
    (test_dir / "__pycache__").mkdir()
    (test_dir / "node_modules").mkdir()
    (test_dir / "regular_file.txt").write_text("content")

    # Search for anything - should not find ignored items
    results = fs.search(
        query="", path=str(test_dir)
    )  # Empty query to test ignore functionality
    # Since empty query returns empty list, let's search for a pattern that could match
    results = fs.search(
        query="_", path=str(test_dir)
    )  # Should match __pycache__ if not ignored

    file_names = {f.name for f in results}
    assert ".DS_Store" not in file_names
    assert "__pycache__" not in file_names
    assert "node_modules" not in file_names


def test_search_directory_and_file_filters(
    test_dir: Path, fs: OSFileSystem
) -> None:
    """Test directory and file filtering parameters work correctly."""
    # Create test files and directories
    (test_dir / "test_file.txt").write_text("content")
    (test_dir / "test_file.py").write_text("# test content")
    test_subdir = test_dir / "test_dir"
    test_subdir.mkdir()
    (test_subdir / "nested_file.txt").write_text("content")

    # Test searching for files only
    results = fs.search(query="test", path=str(test_dir), file=True)
    file_results = [f for f in results if not f.is_directory]
    dir_results = [f for f in results if f.is_directory]
    assert len(file_results) > 0, "Should find files when file=True"
    assert len(dir_results) == 0, "Should not find directories when file=True"

    # Test searching for directories only
    results = fs.search(query="test", path=str(test_dir), directory=True)
    file_results = [f for f in results if not f.is_directory]
    dir_results = [f for f in results if f.is_directory]
    assert len(dir_results) > 0, "Should find directories when directory=True"
    assert len(file_results) == 0, "Should not find files when directory=True"

    # Test searching for both (default behavior)
    results = fs.search(query="test", path=str(test_dir))
    file_results = [f for f in results if not f.is_directory]
    dir_results = [f for f in results if f.is_directory]
    assert len(file_results) > 0, "Should find files with no filter"
    assert len(dir_results) > 0, "Should find directories with no filter"

    # Test with both file=False and directory=False should work like no filter
    results_no_filter = fs.search(query="test", path=str(test_dir))
    results_both_false = fs.search(
        query="test", path=str(test_dir), file=False, directory=False
    )
    assert len(results_no_filter) == len(results_both_false), (
        "Both false should be same as no filter"
    )


def test_search_handles_permission_errors(
    test_dir: Path, fs: OSFileSystem
) -> None:
    """Test search gracefully handles permission errors."""
    # Create a regular file that we can access
    (test_dir / "accessible.txt").write_text("content")

    # Search should not crash even if there are permission issues
    results = fs.search(query="accessible", path=str(test_dir))
    file_names = {f.name for f in results}
    assert "accessible.txt" in file_names


def test_search_nonexistent_path(fs: OSFileSystem) -> None:
    """Test search with nonexistent path returns empty results."""
    results = fs.search(query="test", path="/nonexistent/path")
    assert results == []


def test_search_default_path(fs: OSFileSystem, monkeypatch) -> None:
    """Test search uses root path when path is None."""
    # Mock get_root to return a known directory
    test_root = "/tmp"
    monkeypatch.setattr(fs, "get_root", lambda: test_root)

    # This should not crash (though results may be empty)
    results = fs.search(query="test", path=None)
    assert isinstance(results, list)


def test_search_includes_file_metadata(
    test_dir: Path, fs: OSFileSystem
) -> None:
    """Test search results include proper file metadata."""
    test_file = test_dir / "metadata_test.txt"
    test_file.write_text("content")

    results = fs.search(query="metadata", path=str(test_dir))

    assert len(results) == 1
    file_info = results[0]
    assert file_info.name == "metadata_test.txt"
    assert file_info.path == str(test_file)
    assert file_info.id == str(test_file)
    assert file_info.is_directory is False
    assert file_info.is_marimo_file is False
    assert file_info.last_modified is not None
