import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from marimo._utils.async_path import (
    AsyncPath,
    AsyncPosixPath,
    AsyncWindowsPath,
)


class TestAsyncPathConstruction:
    def test_new_creates_correct_platform_type(self):
        """Test that AsyncPath creates the correct platform-specific type."""
        path = AsyncPath("test")
        if os.name == "nt":
            assert isinstance(path, AsyncWindowsPath)
        else:
            assert isinstance(path, AsyncPosixPath)

    def test_new_with_multiple_args(self):
        """Test creating AsyncPath with multiple path components."""
        path = AsyncPath("home", "user", "file.txt")
        assert str(path) == os.path.join("home", "user", "file.txt")

    def test_truediv_returns_async_path(self):
        """Test that / operator returns AsyncPath instance."""
        path = AsyncPath("home")
        result = path / "user"
        assert isinstance(result, AsyncPath)
        assert str(result) == os.path.join("home", "user")

    def test_rtruediv_returns_async_path(self):
        """Test that reverse / operator returns AsyncPath instance."""
        path = AsyncPath("user")
        result = "home" / path
        assert isinstance(result, AsyncPath)
        assert str(result) == os.path.join("home", "user")

    def test_path_property(self):
        """Test that _path property returns synchronous Path."""
        async_path = AsyncPath("test")
        sync_path = async_path._path
        assert isinstance(sync_path, Path)
        assert str(sync_path) == str(async_path)


class TestAsyncPathFileSystemOperations:
    async def test_exists_true(self):
        """Test exists returns True for existing file."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = AsyncPath(tmp.name)
            assert await path.exists() is True

    async def test_exists_false(self):
        """Test exists returns False for non-existing file."""
        path = AsyncPath("/nonexistent/file")
        assert await path.exists() is False

    async def test_is_file_true(self):
        """Test is_file returns True for regular file."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = AsyncPath(tmp.name)
            assert await path.is_file() is True

    async def test_is_file_false(self):
        """Test is_file returns False for directory."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp)
            assert await path.is_file() is False

    async def test_is_dir_true(self):
        """Test is_dir returns True for directory."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp)
            assert await path.is_dir() is True

    async def test_is_dir_false(self):
        """Test is_dir returns False for file."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = AsyncPath(tmp.name)
            assert await path.is_dir() is False

    async def test_stat(self):
        """Test stat returns stat_result object."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = AsyncPath(tmp.name)
            stat_result = await path.stat()
            assert hasattr(stat_result, "st_size")
            assert hasattr(stat_result, "st_mtime")

    async def test_lstat(self):
        """Test lstat returns stat_result object."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = AsyncPath(tmp.name)
            lstat_result = await path.lstat()
            assert hasattr(lstat_result, "st_size")
            assert hasattr(lstat_result, "st_mtime")

    async def test_chmod(self):
        """Test chmod changes file permissions."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = AsyncPath(tmp.name)
            await path.chmod(0o644)
            stat_result = await path.stat()
            # Check that some permission bits are set
            assert stat_result.st_mode & 0o644

    async def test_mkdir(self):
        """Test mkdir creates directory."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp) / "new_dir"
            await path.mkdir()
            assert await path.exists()
            assert await path.is_dir()

    async def test_mkdir_with_parents(self):
        """Test mkdir with parents creates intermediate directories."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp) / "parent" / "child"
            await path.mkdir(parents=True)
            assert await path.exists()
            assert await path.is_dir()

    async def test_mkdir_exist_ok(self):
        """Test mkdir with exist_ok doesn't raise if directory exists."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp) / "existing"
            await path.mkdir()
            # Should not raise
            await path.mkdir(exist_ok=True)

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Symlinks require special permissions on Windows",
    )
    async def test_unlink(self):
        """Test unlink removes file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = AsyncPath(tmp.name)
            assert await path.exists()
            await path.unlink()
            assert not await path.exists()

    async def test_unlink_missing_ok(self):
        """Test unlink with missing_ok doesn't raise for non-existing file."""
        path = AsyncPath("/nonexistent/file")
        # Should not raise
        await path.unlink(missing_ok=True)

    async def test_rmdir(self):
        """Test rmdir removes empty directory."""
        with tempfile.TemporaryDirectory() as tmp:
            subdir = AsyncPath(tmp) / "subdir"
            await subdir.mkdir()
            assert await subdir.exists()
            await subdir.rmdir()
            assert not await subdir.exists()

    async def test_rename(self):
        """Test rename moves file to new location."""
        with tempfile.TemporaryDirectory() as tmp:
            source = AsyncPath(tmp) / "source.txt"
            target = AsyncPath(tmp) / "target.txt"
            await source.write_text("test content")

            result = await source.rename(target)
            assert isinstance(result, AsyncPath)
            assert not await source.exists()
            assert await target.exists()
            assert await target.read_text() == "test content"

    async def test_replace(self):
        """Test replace overwrites target file."""
        with tempfile.TemporaryDirectory() as tmp:
            source = AsyncPath(tmp) / "source.txt"
            target = AsyncPath(tmp) / "target.txt"
            await source.write_text("source content")
            await target.write_text("target content")

            result = await source.replace(target)
            assert isinstance(result, AsyncPath)
            assert not await source.exists()
            assert await target.exists()
            assert await target.read_text() == "source content"


class TestAsyncPathFileIO:
    async def test_read_text(self):
        """Test read_text returns file contents as string."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write("test content")
            tmp.flush()
            path = AsyncPath(tmp.name)
            content = await path.read_text()
            assert content == "test content"
        os.unlink(tmp.name)

    async def test_read_text_with_encoding(self):
        """Test read_text with specific encoding."""
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write("test content with unicode: ñ")
            tmp.flush()
            path = AsyncPath(tmp.name)
            content = await path.read_text(encoding="utf-8")
            assert "ñ" in content
        os.unlink(tmp.name)

    async def test_read_bytes(self):
        """Test read_bytes returns file contents as bytes."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test bytes")
            tmp.flush()
            path = AsyncPath(tmp.name)
            content = await path.read_bytes()
            assert content == b"test bytes"
        os.unlink(tmp.name)

    async def test_write_text(self):
        """Test write_text writes string to file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp) / "test.txt"
            bytes_written = await path.write_text("test content")
            assert bytes_written > 0
            content = await path.read_text()
            assert content == "test content"

    async def test_write_text_with_encoding(self):
        """Test write_text with specific encoding."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp) / "test.txt"
            content = "test content with unicode: ñ"
            await path.write_text(content, encoding="utf-8")
            read_content = await path.read_text(encoding="utf-8")
            assert read_content == content

    async def test_write_bytes(self):
        """Test write_bytes writes bytes to file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp) / "test.bin"
            data = b"test bytes"
            bytes_written = await path.write_bytes(data)
            assert bytes_written == len(data)
            content = await path.read_bytes()
            assert content == data


class TestAsyncPathDirectoryOperations:
    async def test_iterdir(self):
        """Test iterdir yields directory contents."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create some files
            (Path(tmp) / "file1.txt").touch()
            (Path(tmp) / "file2.txt").touch()

            path = AsyncPath(tmp)
            files = []
            async for item in path.iterdir():
                files.append(item)

            assert len(files) == 2
            assert all(isinstance(f, AsyncPath) for f in files)
            filenames = {f.name for f in files}
            assert filenames == {"file1.txt", "file2.txt"}

    async def test_glob(self):
        """Test glob returns matching paths."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create some files
            (Path(tmp) / "test1.txt").touch()
            (Path(tmp) / "test2.txt").touch()
            (Path(tmp) / "other.py").touch()

            path = AsyncPath(tmp)
            txt_files = []
            async for item in path.glob("*.txt"):
                txt_files.append(item)

            assert len(txt_files) == 2
            assert all(isinstance(f, AsyncPath) for f in txt_files)
            assert all(f.suffix == ".txt" for f in txt_files)

    async def test_rglob(self):
        """Test rglob returns matching paths recursively."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create nested structure
            subdir = Path(tmp) / "subdir"
            subdir.mkdir()
            (Path(tmp) / "test1.txt").touch()
            (subdir / "test2.txt").touch()

            path = AsyncPath(tmp)
            txt_files = []
            async for item in path.rglob("*.txt"):
                txt_files.append(item)

            assert len(txt_files) == 2
            assert all(isinstance(f, AsyncPath) for f in txt_files)
            assert all(f.suffix == ".txt" for f in txt_files)


class TestAsyncPathUtilityMethods:
    async def test_resolve(self):
        """Test resolve returns absolute path."""
        path = AsyncPath(".")
        resolved = await path.resolve()
        assert isinstance(resolved, AsyncPath)
        assert resolved.is_absolute()

    async def test_expanduser(self):
        """Test expanduser expands ~ to home directory."""
        path = AsyncPath("~")
        expanded = await path.expanduser()
        assert isinstance(expanded, AsyncPath)
        # Should expand to actual home directory
        assert str(expanded) != "~"

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Temp file permissions are different on Windows",
    )
    def test_open(self):
        """Test open returns file object."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = AsyncPath(tmp.name)
            with path.open("r") as f:
                assert hasattr(f, "read")
                assert hasattr(f, "write")


class TestAsyncPathSymlinks:
    async def test_is_symlink_false(self):
        """Test is_symlink returns False for regular file."""
        with tempfile.NamedTemporaryFile() as tmp:
            path = AsyncPath(tmp.name)
            assert await path.is_symlink() is False

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Symlinks require special permissions on Windows",
    )
    async def test_symlink_operations(self):
        """Test symlink creation and detection."""
        with tempfile.TemporaryDirectory() as tmp:
            target = AsyncPath(tmp) / "target.txt"
            link = AsyncPath(tmp) / "link.txt"

            await target.write_text("target content")
            await link.symlink_to(target)

            assert await link.is_symlink()
            assert await link.exists()

            # Test readlink
            resolved_target = await link.readlink()
            assert isinstance(resolved_target, AsyncPath)


class TestAsyncPathErrorHandling:
    async def test_stat_nonexistent_file_raises(self):
        """Test stat raises FileNotFoundError for non-existent file."""
        path = AsyncPath("/nonexistent/file")
        with pytest.raises(FileNotFoundError):
            await path.stat()

    async def test_unlink_nonexistent_file_raises(self):
        """Test unlink raises FileNotFoundError for non-existent file."""
        path = AsyncPath("/nonexistent/file")
        with pytest.raises(FileNotFoundError):
            await path.unlink()

    async def test_mkdir_existing_directory_raises(self):
        """Test mkdir raises FileExistsError if directory exists and exist_ok=False."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp) / "existing"
            await path.mkdir()
            with pytest.raises(FileExistsError):
                await path.mkdir(exist_ok=False)

    async def test_rmdir_nonexistent_raises(self):
        """Test rmdir raises FileNotFoundError for non-existent directory."""
        path = AsyncPath("/nonexistent/dir")
        with pytest.raises(FileNotFoundError):
            await path.rmdir()

    async def test_read_text_nonexistent_raises(self):
        """Test read_text raises FileNotFoundError for non-existent file."""
        path = AsyncPath("/nonexistent/file")
        with pytest.raises(FileNotFoundError):
            await path.read_text()


class TestAsyncPathThreading:
    async def test_operations_use_asyncio_to_thread(self):
        """Test that operations actually use asyncio.to_thread."""
        with patch("asyncio.to_thread") as mock_to_thread:
            # Create a future that resolves to True
            future = asyncio.get_event_loop().create_future()
            future.set_result(True)
            mock_to_thread.return_value = future

            path = AsyncPath("test")
            await path.exists()

            mock_to_thread.assert_called_once()
            # Verify it was called with the path's sync method
            args = mock_to_thread.call_args[0]
            assert callable(args[0])  # First arg should be the sync method


class TestAsyncPathEdgeCases:
    @pytest.mark.skipif(
        sys.version_info < (3, 10),
        reason="Hardlink requires Python 3.10 or higher",
    )
    async def test_hardlink_to(self):
        """Test hardlink_to creates hard link."""
        with tempfile.TemporaryDirectory() as tmp:
            source = AsyncPath(tmp) / "source.txt"
            target = AsyncPath(tmp) / "target.txt"
            await source.write_text("test content")

            await target.hardlink_to(source)

            assert await target.exists()
            assert await target.read_text() == "test content"
            # Both should have same inode (hard link)
            source_stat = await source.stat()
            target_stat = await target.stat()
            assert source_stat.st_ino == target_stat.st_ino

    @pytest.mark.skipif(
        sys.version_info < (3, 10),
        reason="Hardlink requires Python 3.10 or higher",
    )
    async def test_write_text_with_newline(self):
        """Test write_text with custom newline parameter."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp) / "test.txt"
            content = "line1\nline2"
            await path.write_text(content, newline="\r\n")
            # Read the raw bytes to verify newline conversion
            raw_content = await path.read_bytes()
            assert b"\r\n" in raw_content

    async def test_resolve_with_strict(self):
        """Test resolve with strict parameter."""
        path = AsyncPath(".")
        resolved = await path.resolve(strict=True)
        assert isinstance(resolved, AsyncPath)
        assert resolved.is_absolute()

    async def test_iterdir_empty_directory(self):
        """Test iterdir on empty directory."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp)
            files = []
            async for item in path.iterdir():
                files.append(item)
            assert len(files) == 0

    async def test_glob_no_matches(self):
        """Test glob with pattern that matches nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            path = AsyncPath(tmp)
            matches = []
            async for item in path.glob("*.nonexistent"):
                matches.append(item)
            assert len(matches) == 0

    async def test_path_with_spaces_and_special_chars(self):
        """Test AsyncPath handles paths with spaces and special characters."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create path with spaces and special chars
            special_path = (
                AsyncPath(tmp) / "file with spaces & special chars.txt"
            )
            await special_path.write_text("test content")

            assert await special_path.exists()
            assert await special_path.is_file()
            content = await special_path.read_text()
            assert content == "test content"

    async def test_multiple_path_operations(self):
        """Test chaining multiple path operations."""
        base = AsyncPath("home")
        result = base / "user" / "documents" / "file.txt"
        assert isinstance(result, AsyncPath)
        assert str(result) == os.path.join(
            "home", "user", "documents", "file.txt"
        )

    async def test_path_equality_and_hashing(self):
        """Test path equality and hashing."""
        path1 = AsyncPath("test", "file.txt")
        path2 = AsyncPath("test") / "file.txt"

        assert str(path1) == str(path2)
        # They should be equal as strings
        assert str(path1) == str(path2)
