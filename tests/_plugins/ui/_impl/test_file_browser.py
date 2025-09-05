from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import pytest

from marimo._plugins.ui._impl.file_browser import (
    FileBrowserFileInfo,
    ListDirectoryArgs,
    ListDirectoryResponse,
    file_browser,
)


def test_file_browser_init() -> None:
    # Use a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        fb = file_browser(initial_path=temp_dir)
        assert isinstance(fb._initial_path, Path)
        assert str(fb._initial_path) == str(Path(temp_dir).resolve())
        assert fb._selection_mode == "file"
        assert fb._filetypes == set()
        assert fb._restrict_navigation is False

        # Test with custom filetypes
        custom_filetypes = [".txt", ".csv"]
        fb = file_browser(
            initial_path=temp_dir,
            filetypes=custom_filetypes,
            selection_mode="directory",
            restrict_navigation=True,
        )
        assert fb._initial_path == Path(temp_dir).resolve()
        assert fb._filetypes == set(custom_filetypes)
        assert fb._selection_mode == "directory"
        assert fb._restrict_navigation is True


def test_list_directory() -> None:
    fb = file_browser(
        initial_path=Path.cwd(), filetypes=[".txt"], selection_mode="file"
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(Path.cwd())))
    assert isinstance(response, ListDirectoryResponse)
    assert isinstance(response.total_count, int)
    assert isinstance(response.is_truncated, bool)
    assert hasattr(response, "total_count")
    assert hasattr(response, "is_truncated")

    for file_info in response.files:
        assert file_info["is_directory"] or file_info["path"].endswith(
            tuple(fb._filetypes)
        )


def test_navigation_restriction() -> None:
    fb = file_browser(initial_path=Path.cwd(), restrict_navigation=True)
    with pytest.raises(RuntimeError) as e:
        fb._list_directory(ListDirectoryArgs(path=str(Path.cwd().parent)))
    assert "Navigation is restricted" in str(e.value)


def test_name_method() -> None:
    fb = file_browser(initial_path=Path.cwd())
    fb._value = [
        FileBrowserFileInfo(
            id="1",
            path=Path("/some/path/file.txt"),
            name="file.txt",
            is_directory=False,
        )
    ]
    assert fb.name(0) == "file.txt"
    assert fb.name(1) is None


def test_path_method() -> None:
    fb = file_browser(initial_path=Path.cwd())
    fb._value = [
        FileBrowserFileInfo(
            id="1",
            path=Path("/some/path/file.txt"),
            name="file.txt",
            is_directory=False,
        )
    ]
    assert fb.path(0) == Path("/some/path/file.txt")
    assert fb.path(1) is None


def test_natural_sorting(tmp_path: Path) -> None:
    """Test that files are sorted using natural sort order."""
    # Create test files with names that should be naturally sorted
    test_files = [
        "file10.txt",
        "file2.txt",
        "file1.txt",
        "file20.txt",
        "fileB.txt",
        "fileA.txt",
        "file100.txt",
    ]

    for filename in test_files:
        (tmp_path / filename).touch()

    fb = file_browser(initial_path=tmp_path)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # Extract file names from response
    file_names = [f["name"] for f in response.files if not f["is_directory"]]

    # Expected natural sort order
    expected_order = [
        "file1.txt",
        "file2.txt",
        "file10.txt",
        "file20.txt",
        "file100.txt",
        "fileA.txt",
        "fileB.txt",
    ]

    assert file_names == expected_order


def test_directories_sorted_before_files(tmp_path: Path) -> None:
    """Test that directories are sorted before files."""
    # Create test directories and files
    (tmp_path / "z_directory").mkdir()
    (tmp_path / "a_directory").mkdir()
    (tmp_path / "a_file.txt").touch()
    (tmp_path / "z_file.txt").touch()

    fb = file_browser(initial_path=tmp_path)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # Extract names and types
    items = [(f["name"], f["is_directory"]) for f in response.files]

    # Check that all directories come before all files
    directory_names = [name for name, is_dir in items if is_dir]
    file_names = [name for name, is_dir in items if not is_dir]

    # Directories should be sorted naturally among themselves
    assert directory_names == ["a_directory", "z_directory"]
    # Files should be sorted naturally among themselves
    assert file_names == ["a_file.txt", "z_file.txt"]

    # All directory names should come before all file names in the full list
    all_names = [name for name, _ in items]
    directory_end_index = len(directory_names)
    assert all_names[:directory_end_index] == directory_names
    assert all_names[directory_end_index:] == file_names


def test_mixed_alphanumeric_sorting(tmp_path: Path) -> None:
    """Test natural sorting with mixed alphanumeric patterns."""
    test_items = [
        ("dir100", True),  # directory
        ("dir2", True),  # directory
        ("dir10", True),  # directory
        ("file100.txt", False),  # file
        ("file2.txt", False),  # file
        ("file10.txt", False),  # file
    ]

    # Create test directories and files
    for name, is_dir in test_items:
        if is_dir:
            (tmp_path / name).mkdir()
        else:
            (tmp_path / name).touch()

    fb = file_browser(initial_path=tmp_path)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # Extract names preserving order from response
    result_names = [f["name"] for f in response.files]

    # Expected order: directories first (naturally sorted), then files (naturally sorted)
    expected_order = [
        "dir2",  # directories first, naturally sorted
        "dir10",
        "dir100",
        "file2.txt",  # files second, naturally sorted
        "file10.txt",
        "file100.txt",
    ]

    assert result_names == expected_order


@pytest.mark.skipif(
    sys.version_info <= (3, 12), reason="Only works with Python 3.12+"
)
def test_extended_path_class(tmp_path: Path) -> None:
    class CustomPath(Path):
        pass

    (tmp_path / "file.txt").touch()

    fb = file_browser(initial_path=CustomPath(tmp_path), limit=1)
    response = fb._list_directory(
        ListDirectoryArgs(path=str(tmp_path)),
    )
    assert isinstance(response, ListDirectoryResponse)
    for file_info in response.files:
        assert isinstance(file_info["path"], str)

    # Convert the value
    value = fb._convert_value(response.files)
    assert isinstance(value, tuple)
    assert len(value) == 1
    assert isinstance(value[0], FileBrowserFileInfo)
    assert isinstance(value[0].path, CustomPath)

    class CustomPathWithClient(Path):
        def __init__(self, path: Path, client: Optional[Any] = None) -> None:
            super().__init__(path)
            self.client = client

        def resolve(self) -> CustomPathWithClient:
            return CustomPathWithClient(super().resolve(), self.client)

    fb = file_browser(
        initial_path=CustomPathWithClient(tmp_path, "custom_client")
    )
    response = fb._list_directory(
        ListDirectoryArgs(path=str(tmp_path)),
    )
    value = fb._convert_value(response.files)
    assert isinstance(value, tuple)
    assert len(value) == 1
    assert isinstance(value[0], FileBrowserFileInfo)
    assert isinstance(value[0].path, CustomPathWithClient)
    assert value[0].path.client == "custom_client"


def test_validation() -> None:
    with pytest.raises(ValueError) as e:
        file_browser(initial_path="invalid", selection_mode="invalid")
    assert "Value must be one of" in str(e.value)


def test_limit_arg(tmp_path: Path) -> None:
    """Test limit argument behavior: defaults and explicit overrides."""
    fb_default = file_browser(initial_path=tmp_path)
    assert fb_default._limit == 10000  # High limit for local filesystem

    fb_custom = file_browser(initial_path=tmp_path, limit=25)
    assert fb_custom._limit == 25

    fb_zero = file_browser(initial_path=tmp_path, limit=0)
    assert fb_zero._limit == 0


def test_is_truncated_true_when_limit_exceeded(tmp_path: Path) -> None:
    """Test is_truncated=True when directory has more files than limit."""
    # Create more files than the limit
    for i in range(10):
        (tmp_path / f"file{i}.txt").touch()

    fb = file_browser(initial_path=tmp_path, limit=5)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert response.is_truncated is True
    assert response.total_count == 10
    assert len(response.files) == 5


def test_is_truncated_false_when_under_limit(tmp_path: Path) -> None:
    """Test is_truncated=False when directory has fewer files than limit."""
    # Create fewer files than the limit
    for i in range(3):
        (tmp_path / f"file{i}.txt").touch()

    fb = file_browser(initial_path=tmp_path, limit=5)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert response.is_truncated is False
    assert response.total_count == 3
    assert len(response.files) == 3


def test_is_truncated_false_when_exactly_at_limit(tmp_path: Path) -> None:
    """Test is_truncated=False when directory has exactly limit number of files."""
    # Create exactly the limit number of files
    for i in range(5):
        (tmp_path / f"file{i}.txt").touch()

    fb = file_browser(initial_path=tmp_path, limit=5)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert response.is_truncated is False
    assert response.total_count == 5
    assert len(response.files) == 5


def test_total_count_includes_all_items(tmp_path: Path) -> None:
    """Test that total_count reflects all files in directory, not just displayed ones."""
    # Create mix of files and directories
    for i in range(8):
        (tmp_path / f"file{i}.txt").touch()
    for i in range(3):
        (tmp_path / f"dir{i}").mkdir()

    fb = file_browser(initial_path=tmp_path, limit=5)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    assert response.total_count == 11  # All files and directories
    assert len(response.files) == 5  # Only displayed items
    assert response.is_truncated is True


def test_is_truncated_with_filetype_filtering_edge_case(
    tmp_path: Path,
) -> None:
    """Test is_truncated when filtering creates ambiguity about remaining files."""
    # Create files where filtering matters for truncation detection
    (tmp_path / "file1.txt").touch()
    (tmp_path / "file2.txt").touch()
    (tmp_path / "file3.txt").touch()
    (tmp_path / "file4.py").touch()
    (tmp_path / "file5.py").touch()

    fb = file_browser(initial_path=tmp_path, filetypes=[".txt"], limit=2)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))

    # We should show two .txt files, but there's a third .txt file we didn't process
    assert response.total_count == 5
    assert len(response.files) == 2
    assert response.is_truncated is True


def test_ignore_empty_dirs_initialization(tmp_path: Path) -> None:
    """Test that ignore_empty_dirs parameter is properly initialized."""
    # Creates:
    # tmp_path/  (empty directory for initialization testing)
    
    # Default should be False
    fb_default = file_browser(initial_path=tmp_path)
    assert fb_default._ignore_empty_dirs is False

    # Explicit True
    fb_true = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    assert fb_true._ignore_empty_dirs is True

    # Explicit False
    fb_false = file_browser(initial_path=tmp_path, ignore_empty_dirs=False)
    assert fb_false._ignore_empty_dirs is False


def test_ignore_empty_dirs_with_empty_directory(tmp_path: Path) -> None:
    """Test that empty directories are hidden when ignore_empty_dirs=True."""
    # Create structure with empty directories
    # /
    # ├── empty_dir / (empty directory)
    # ├── another_empty / (empty directory)
    # └── file.txt(empty file)

    (tmp_path / "empty_dir").mkdir()
    (tmp_path / "another_empty").mkdir()
    (tmp_path / "file.txt").touch()

    # Without ignore_empty_dirs (should show empty directories)
    fb_false = file_browser(initial_path=tmp_path, ignore_empty_dirs=False)
    response_false = fb_false._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response_false.files if f["is_directory"]]
    file_names = [f["name"] for f in response_false.files if not f["is_directory"]]
    
    assert "empty_dir" in directory_names
    assert "another_empty" in directory_names
    assert "file.txt" in file_names

    # With ignore_empty_dirs (should hide empty directories)
    fb_true = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    response_true = fb_true._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response_true.files if f["is_directory"]]
    file_names = [f["name"] for f in response_true.files if not f["is_directory"]]
    
    assert "empty_dir" not in directory_names
    assert "another_empty" not in directory_names
    assert "file.txt" in file_names


def test_ignore_empty_dirs_with_nested_empty_directories(tmp_path: Path) -> None:
    """Test that deeply nested empty directories are hidden."""
    # Creates:
    # tmp_path/
    # ├── level1/
    # │   └── level2/
    # │       └── level3/          (nested empty structure)
    # └── non_empty/
    #     └── file.txt             (directory with files)
    
    # Create nested empty directory structure
    nested_path = tmp_path / "level1" / "level2" / "level3"
    nested_path.mkdir(parents=True)
    
    # Create a non-empty directory for comparison
    non_empty_dir = tmp_path / "non_empty"
    non_empty_dir.mkdir()
    (non_empty_dir / "file.txt").touch()

    fb = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    
    # Should hide the nested empty structure but show the non-empty directory
    assert "level1" not in directory_names
    assert "non_empty" in directory_names


def test_ignore_empty_dirs_with_files_in_subdirectories(tmp_path: Path) -> None:
    """Test that directories with files in subdirectories are shown."""
    # Creates:
    # tmp_path/
    # ├── has_files/
    # │   └── nested/
    # │       └── deep/
    # │           └── deep_file.txt    (file buried deep inside)
    # └── empty_dir/                   (truly empty)
    
    # Create directory structure with files deep inside
    deep_dir = tmp_path / "has_files" / "nested" / "deep"
    deep_dir.mkdir(parents=True)
    (deep_dir / "deep_file.txt").touch()
    
    # Create empty directory for comparison
    (tmp_path / "empty_dir").mkdir()

    fb = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    
    # Should show directory that has files somewhere inside
    assert "has_files" in directory_names
    # Should hide truly empty directory
    assert "empty_dir" not in directory_names


def test_ignore_empty_dirs_respects_filetype_filter(tmp_path: Path) -> None:
    """Test that ignore_empty_dirs respects filetype filtering."""
    # Creates:
    # tmp_path/
    # ├── python_only/
    # │   └── script.py        (has files, but wrong type)
    # ├── text_files/
    # │   └── document.txt     (has files of correct type)
    # └── empty_dir/           (truly empty)
    
    # Create directory with only .py files (no .txt files)
    py_dir = tmp_path / "python_only"
    py_dir.mkdir()
    (py_dir / "script.py").touch()
    
    # Create directory with .txt files
    txt_dir = tmp_path / "text_files"
    txt_dir.mkdir()
    (txt_dir / "document.txt").touch()
    
    # Create empty directory
    (tmp_path / "empty_dir").mkdir()

    # Filter for .txt files only with ignore_empty_dirs=True
    fb = file_browser(
        initial_path=tmp_path, 
        filetypes=[".txt"], 
        ignore_empty_dirs=True
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    
    # Should show directory with .txt files
    assert "text_files" in directory_names
    # Should hide directory with only .py files (filtered out)
    assert "python_only" not in directory_names
    # Should hide empty directory
    assert "empty_dir" not in directory_names


def test_ignore_empty_dirs_mixed_with_files(tmp_path: Path) -> None:
    """Test ignore_empty_dirs behavior in a directory with mixed content."""
    # Creates:
    # tmp_path/
    # ├── root_file.txt        (file at root level)
    # ├── good_dir/
    # │   └── subfile.txt      (directory with files)
    # ├── empty_dir/           (truly empty)
    # └── nested_empty/
    #     └── level2/          (nested empty structure)
    
    # Create files at root level
    (tmp_path / "root_file.txt").touch()
    
    # Create non-empty subdirectory
    good_dir = tmp_path / "good_dir"
    good_dir.mkdir()
    (good_dir / "subfile.txt").touch()
    
    # Create empty subdirectory
    (tmp_path / "empty_dir").mkdir()
    
    # Create directory with nested empty directories only
    nested_empty = tmp_path / "nested_empty" / "level2"
    nested_empty.mkdir(parents=True)

    fb = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    # Separate directories and files
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    file_names = [f["name"] for f in response.files if not f["is_directory"]]
    
    # Should show non-empty directory and root file
    assert "good_dir" in directory_names
    assert "root_file.txt" in file_names
    
    # Should hide empty directories
    assert "empty_dir" not in directory_names
    assert "nested_empty" not in directory_names


def test_ignore_empty_dirs_directory_selection_mode(tmp_path: Path) -> None:
    """Test ignore_empty_dirs with selection_mode='directory'."""
    # Creates:
    # tmp_path/
    # ├── empty_dir/           (empty directory)
    # ├── good_dir/
    # │   └── file.txt         (directory with files)
    # └── file.txt             (file - filtered out in directory mode)
    
    # Create empty directory
    (tmp_path / "empty_dir").mkdir()
    
    # Create directory with files
    good_dir = tmp_path / "good_dir"
    good_dir.mkdir()
    (good_dir / "file.txt").touch()
    
    # Create a file (should be filtered out in directory mode)
    (tmp_path / "file.txt").touch()

    fb = file_browser(
        initial_path=tmp_path, 
        selection_mode="directory",
        ignore_empty_dirs=True
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    # All results should be directories (selection_mode filters files)
    for item in response.files:
        assert item["is_directory"] is True
    
    directory_names = [f["name"] for f in response.files]
    
    # Should show non-empty directory
    assert "good_dir" in directory_names
    # Should hide empty directory
    assert "empty_dir" not in directory_names


def test_ignore_empty_dirs_respects_max_depth(tmp_path: Path) -> None:
    """Test that recursion depth is limited to prevent stack overflow."""
    # Creates:
    # tmp_path/
    # ├── shallow_with_files/
    # │   └── file.txt         (file at shallow depth)
    # ├── deep_structure/
    # │   └── level1/
    # │       └── level2/
    # │           └── ... (many levels)
    # │               └── deep_file.txt (file beyond max_depth)
    # └── empty_dir/           (truly empty)
    
    # Create shallow directory with files
    shallow_dir = tmp_path / "shallow_with_files"
    shallow_dir.mkdir()
    (shallow_dir / "file.txt").touch()
    
    # Create very deep directory structure (beyond max_depth)
    deep_path = tmp_path / "deep_structure"
    current = deep_path
    # Create 102 levels deep (beyond default max_depth of 100)
    for i in range(102):
        current = current / f"level{i}"
    current.mkdir(parents=True)
    (current / "deep_file.txt").touch()
    
    # Create empty directory for comparison
    (tmp_path / "empty_dir").mkdir()

    fb = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    
    # Should show shallow directory with files
    assert "shallow_with_files" in directory_names
    # Should show deep structure (assumes has files when max_depth reached)
    assert "deep_structure" in directory_names
    # Should hide empty directory
    assert "empty_dir" not in directory_names


def test_ignore_empty_dirs_max_depth_boundary_conditions(tmp_path: Path) -> None:
    """Test boundary conditions around max_depth limit."""
    # Creates:
    # tmp_path/
    # ├── depth_100_with_file/
    # │   └── level0/level1/.../level99/
    # │       └── file.txt         (file at exactly depth 100)
    # ├── depth_101_with_file/  
    # │   └── level0/level1/.../level100/
    # │       └── file.txt         (file at depth 101 - beyond limit)
    # ├── depth_100_empty/
    # │   └── level0/level1/.../level99/  (empty at depth 100)
    # └── depth_101_empty/
    #     └── level0/level1/.../level100/ (empty at depth 101 - beyond limit)
    
    # Test case 1: File at exactly depth 100 (should be found)
    depth_100_with_file = tmp_path / "depth_100_with_file"
    current = depth_100_with_file
    for i in range(100):  # Create 100 levels deep
        current = current / f"level{i}"
    current.mkdir(parents=True)
    (current / "file.txt").touch()
    
    # Test case 2: File at depth 101 (beyond limit, should assume has files)
    depth_101_with_file = tmp_path / "depth_101_with_file"
    current = depth_101_with_file
    for i in range(101):  # Create 101 levels deep
        current = current / f"level{i}"
    current.mkdir(parents=True)
    (current / "file.txt").touch()
    
    # Test case 3: Empty at exactly depth 99 (should be detected as empty)
    depth_99_empty = tmp_path / "depth_99_empty"
    current = depth_99_empty
    for i in range(99):  # Create 99 levels deep (within limit)
        current = current / f"level{i}"
    current.mkdir(parents=True)  # No file created
    
    # Test case 4: Empty at depth 100 (at limit, should assume has files)
    depth_100_empty = tmp_path / "depth_100_empty"
    current = depth_100_empty
    for i in range(100):
        current = current / f"level{i}"
    current.mkdir(parents=True)  # No file created

    fb = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    
    # Should show directory with file at depth 100 (within limit)
    assert "depth_100_with_file" in directory_names
    # Should show directory with file at depth 101 (beyond limit, assumes has files)
    assert "depth_101_with_file" in directory_names
    # Should hide empty directory at depth 99 (within limit, detected as empty)
    assert "depth_99_empty" not in directory_names
    # Should show empty directory at depth 100 (at limit, assumes has files for safety)
    assert "depth_100_empty" in directory_names


def test_ignore_empty_dirs_case_insensitive_filetypes(tmp_path: Path) -> None:
    """Test that filetype filtering is case-insensitive."""
    # Creates:
    # tmp_path/
    # ├── mixed_case_files/
    # │   ├── document.TXT     (uppercase extension)
    # │   ├── script.Py        (mixed case extension)
    # │   └── data.CSV         (uppercase extension)
    # ├── wrong_type_files/
    # │   └── archive.zip      (different extension)
    # └── empty_dir/           (truly empty)
    
    # Create directory with mixed case extensions
    mixed_case_dir = tmp_path / "mixed_case_files"
    mixed_case_dir.mkdir()
    (mixed_case_dir / "document.TXT").touch()   # Uppercase
    (mixed_case_dir / "script.Py").touch()      # Mixed case
    (mixed_case_dir / "data.CSV").touch()       # Uppercase
    
    # Create directory with wrong file type
    wrong_type_dir = tmp_path / "wrong_type_files"
    wrong_type_dir.mkdir()
    (wrong_type_dir / "archive.zip").touch()
    
    # Create empty directory
    (tmp_path / "empty_dir").mkdir()

    # Test with lowercase filetypes and mixed input formats
    fb = file_browser(
        initial_path=tmp_path, 
        filetypes=["txt", ".py", ".CSV"],  # Mixed formats: no dot, dot, uppercase
        ignore_empty_dirs=True
    )
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    file_names = [f["name"] for f in response.files if not f["is_directory"]]
    
    # Should show directory with mixed case matching files
    assert "mixed_case_files" in directory_names
    # Should hide directory with non-matching file types  
    assert "wrong_type_files" not in directory_names
    # Should hide empty directory
    assert "empty_dir" not in directory_names
    
    # Also test direct file listing to verify case-insensitive matching
    fb_direct = file_browser(
        initial_path=mixed_case_dir,
        filetypes=["txt", ".py", ".csv"]  # All lowercase
    )
    response_direct = fb_direct._list_directory(ListDirectoryArgs(path=str(mixed_case_dir)))
    direct_files = [f["name"] for f in response_direct.files if not f["is_directory"]]
    
    # Should show all files despite case differences
    assert "document.TXT" in direct_files
    assert "script.Py" in direct_files  
    assert "data.CSV" in direct_files


def test_ignore_empty_dirs_skips_directory_symlinks(tmp_path: Path) -> None:
    """Test that directory symlinks are skipped to prevent infinite loops."""
    # Creates:
    # tmp_path/
    # ├── real_dir/
    # │   └── file.txt         (real directory with files)
    # ├── symlink_to_real_dir@ -> real_dir/  (symlink to real directory)
    # ├── broken_symlink@     (broken symlink)
    # └── empty_dir/           (truly empty)
    
    # Create real directory with files
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    (real_dir / "file.txt").touch()
    
    # Create symlink to real directory
    symlink_dir = tmp_path / "symlink_to_real_dir" 
    symlink_dir.symlink_to(real_dir)
    
    # Create broken symlink
    broken_symlink = tmp_path / "broken_symlink"
    broken_symlink.symlink_to(tmp_path / "nonexistent")
    
    # Create empty directory
    (tmp_path / "empty_dir").mkdir()

    fb = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    
    # Should show real directory with files
    assert "real_dir" in directory_names
    # Should show valid directory symlinks (they're not recursively checked, so treated as potentially having content)
    assert "symlink_to_real_dir" in directory_names
    # Broken symlinks may not appear as directories, so we don't test for them
    # Should hide empty directory
    assert "empty_dir" not in directory_names


def test_ignore_empty_dirs_symlink_loop_protection(tmp_path: Path) -> None:
    """Test protection against symlink loops in deep directory structures."""
    # Creates:
    # tmp_path/
    # ├── loop_start/
    # │   ├── level1/
    # │   │   ├── level2/
    # │   │   │   └── back_to_start@ -> ../../../loop_start/  (creates loop)
    # │   │   └── real_file.txt    (file in the structure)
    # │   └── file.txt             (file at top level)
    # └── empty_dir/               (truly empty)
    
    # Create directory structure with potential for loops
    loop_start = tmp_path / "loop_start"
    loop_start.mkdir()
    (loop_start / "file.txt").touch()
    
    level1 = loop_start / "level1"  
    level1.mkdir()
    
    level2 = level1 / "level2"
    level2.mkdir()
    (level1 / "real_file.txt").touch()  # Add file to make structure non-empty
    
    # Create symlink that would cause infinite loop
    loop_symlink = level2 / "back_to_start"
    loop_symlink.symlink_to(loop_start)
    
    # Create empty directory
    (tmp_path / "empty_dir").mkdir()

    fb = file_browser(initial_path=tmp_path, ignore_empty_dirs=True)
    response = fb._list_directory(ListDirectoryArgs(path=str(tmp_path)))
    
    directory_names = [f["name"] for f in response.files if f["is_directory"]]
    
    # Should show directory with files (symlinks are skipped so no infinite loop)
    assert "loop_start" in directory_names
    # Should hide empty directory
    assert "empty_dir" not in directory_names
    
    # Test should complete without hanging (no infinite loop)
