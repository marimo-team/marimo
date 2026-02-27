# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dirty_equals import IsDatetime, IsPositiveFloat
from inline_snapshot import snapshot

from marimo._data._external_storage.models import DownloadResult, StorageEntry
from marimo._data._external_storage.storage import (
    FsspecFilesystem,
    Obstore,
    normalize_protocol,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._types.ids import VariableName

HAS_OBSTORE = DependencyManager.obstore.has()
HAS_FSSPEC = DependencyManager.fsspec.has()


@pytest.mark.skipif(not HAS_OBSTORE, reason="obstore not installed")
class TestObstore:
    def _make_backend(self, store: Any, name: str = "my_store") -> Obstore:
        return Obstore(store, VariableName(name))

    def test_list_entries(self) -> None:
        now = datetime.now(tz=timezone.utc)
        mock_store = MagicMock()
        mock_store.list_with_delimiter.return_value = {
            "common_prefixes": ["subdir/"],
            "objects": [
                {
                    "path": "file1.txt",
                    "size": 100,
                    "last_modified": now,
                    "e_tag": "abc",
                    "version": None,
                },
                {
                    "path": "dir/file2.txt",
                    "size": 200,
                    "last_modified": now,
                    "e_tag": None,
                    "version": "v1",
                },
            ],
        }

        backend = self._make_backend(mock_store)
        result = backend.list_entries(prefix="some/prefix", limit=10)

        mock_store.list_with_delimiter.assert_called_once_with(
            prefix="some/prefix",
        )
        assert result == snapshot(
            [
                StorageEntry(
                    path="subdir/",
                    kind="directory",
                    size=0,
                    last_modified=None,
                    metadata={},
                    mime_type=None,
                ),
                StorageEntry(
                    path="file1.txt",
                    kind="object",
                    size=100,
                    last_modified=now.timestamp(),
                    metadata={"e_tag": "abc"},
                    mime_type="text/plain",
                ),
                StorageEntry(
                    path="dir/file2.txt",
                    kind="object",
                    size=200,
                    last_modified=now.timestamp(),
                    metadata={"version": "v1"},
                    mime_type="text/plain",
                ),
            ]
        )

    def test_list_entries_empty(self) -> None:
        mock_store = MagicMock()
        mock_store.list_with_delimiter.return_value = {
            "common_prefixes": [],
            "objects": [],
        }

        backend = self._make_backend(mock_store)
        result = backend.list_entries(prefix=None)
        assert result == []

    def test_create_storage_entry_missing_fields(self) -> None:
        mock_store = MagicMock()
        backend = self._make_backend(mock_store)

        entry = backend._create_storage_entry(
            {  # pyright: ignore[reportArgumentType]
                "path": None,
                "size": None,
                "last_modified": None,
                "e_tag": None,
                "version": None,
            }
        )
        assert entry == snapshot(
            StorageEntry(
                path="",
                kind="object",
                size=0,
                last_modified=None,
                metadata={},
                mime_type=None,
            )
        )

    def test_create_storage_entry_with_all_metadata(self) -> None:
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_store = MagicMock()
        backend = self._make_backend(mock_store)

        entry = backend._create_storage_entry(
            {
                "path": "test.csv",
                "size": 500,
                "last_modified": now,
                "e_tag": "etag123",
                "version": "v2",
            }
        )
        assert entry == snapshot(
            StorageEntry(
                path="test.csv",
                kind="object",
                size=500,
                last_modified=now.timestamp(),
                metadata={"e_tag": "etag123", "version": "v2"},
                mime_type="text/csv",
            )
        )

    async def test_get_entry(self) -> None:
        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_store = MagicMock()
        head_result = {
            "path": "test.txt",
            "size": 42,
            "last_modified": now,
            "e_tag": "e1",
            "version": None,
        }
        mock_store.head_async = MagicMock(
            return_value=_async_return(head_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.get_entry("test.txt")
        assert result == snapshot(
            StorageEntry(
                path="test.txt",
                kind="object",
                size=42,
                last_modified=now.timestamp(),
                metadata={"e_tag": "e1"},
                mime_type="text/plain",
            )
        )
        mock_store.head_async.assert_called_once_with("test.txt")

    async def test_download(self) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"hello world")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.download("some/path.txt")
        assert result == b"hello world"
        mock_store.get_async.assert_called_once_with("some/path.txt")

    async def test_download_file(self) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"file content")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.download_file("bucket/data/report.csv")

        assert result == DownloadResult(
            file_bytes=b"file content",
            filename="report.csv",
            ext="csv",
        )

    async def test_download_file_no_extension(self) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"data")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.download_file("bucket/noext")

        assert result == DownloadResult(
            file_bytes=b"data",
            filename="noext",
            ext="bin",
        )

    async def test_download_file_nested_path(self) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"nested")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.download_file("a/b/c/deep.tar.gz")

        assert result == DownloadResult(
            file_bytes=b"nested",
            filename="deep.tar.gz",
            ext="gz",
        )

    async def test_download_file_trailing_dot(self) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"data")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.download_file("bucket/file.")

        assert result == DownloadResult(
            file_bytes=b"data",
            filename="file.",
            ext="bin",
        )

    async def test_download_file_empty_path(self) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"data")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.download_file("")

        assert result == DownloadResult(
            file_bytes=b"data",
            filename="download",
            ext="bin",
        )

    async def test_read_range_full_file_delegates_to_download(self) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"full content")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.read_range("file.txt")
        assert result == b"full content"
        mock_store.get_async.assert_called_once_with("file.txt")

    async def test_read_range_offset_without_length_slices_download(
        self,
    ) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"hello world")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = await backend.read_range("file.txt", offset=6)
        assert result == b"world"
        mock_store.get_async.assert_called_once_with("file.txt")

    async def test_read_range_with_offset_and_length(self) -> None:
        mock_store = MagicMock()
        backend = self._make_backend(mock_store)

        with patch(
            "obstore.get_range_async",
            new_callable=AsyncMock,
            return_value=b"partial",
        ) as mock_get_range:
            result = await backend.read_range(
                "file.txt", offset=10, length=100
            )

        assert result == b"partial"
        mock_get_range.assert_called_once_with(
            mock_store, "file.txt", start=10, length=100
        )

    async def test_read_range_with_length_only(self) -> None:
        mock_store = MagicMock()
        backend = self._make_backend(mock_store)

        with patch(
            "obstore.get_range_async",
            new_callable=AsyncMock,
            return_value=b"first bytes",
        ) as mock_get_range:
            result = await backend.read_range("file.txt", length=50)

        assert result == b"first bytes"
        mock_get_range.assert_called_once_with(
            mock_store, "file.txt", start=0, length=50
        )

    def test_protocol_memory(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        backend = self._make_backend(store)
        assert backend.protocol == "in-memory"

    def test_protocol_local(self) -> None:
        import tempfile

        from obstore.store import LocalStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalStore(tmpdir)
            backend = self._make_backend(store)
            assert backend.protocol == "file"

    def test_root_path_memory(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        backend = self._make_backend(store)
        assert backend.root_path is None

    def test_root_path_local(self) -> None:
        import tempfile

        from obstore.store import LocalStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalStore(tmpdir)
            backend = self._make_backend(store)
            # LocalStore without a prefix should return None
            root = backend.root_path
            # This depends on whether there's a prefix; for a bare LocalStore it's None
            assert root is None or isinstance(root, str)

    def test_root_path_s3_with_prefix(self) -> None:
        from obstore.store import S3Store

        store = S3Store("test-bucket", prefix="my/prefix", skip_signature=True)
        backend = self._make_backend(store)
        root = backend.root_path
        assert root is not None
        assert "my/prefix" in str(root)

    def test_root_path_s3_without_prefix(self) -> None:
        from obstore.store import S3Store

        store = S3Store("test-bucket", skip_signature=True)
        backend = self._make_backend(store)
        root = backend.root_path
        assert root == "test-bucket"

    def test_is_compatible_with_obstore(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        assert Obstore.is_compatible(store) is True

    def test_is_compatible_with_non_obstore(self) -> None:
        assert Obstore.is_compatible("not a store") is False
        assert Obstore.is_compatible(42) is False
        assert Obstore.is_compatible(None) is False

    async def test_sign_download_url_returns_none_for_non_cloud_store(
        self,
    ) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        backend = self._make_backend(store)
        result = await backend.sign_download_url("some/path.txt")
        assert result is None

    async def test_sign_download_url_returns_none_for_local_store(
        self,
    ) -> None:
        from obstore.store import LocalStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = LocalStore(tmpdir)
            backend = self._make_backend(store)
            result = await backend.sign_download_url("some/path.txt")
            assert result is None

    async def test_sign_download_url_calls_sign_async_for_s3(self) -> None:
        from obstore.store import S3Store

        store = S3Store("test-bucket", skip_signature=True)
        backend = self._make_backend(store)

        with patch(
            "obstore.sign_async",
            new_callable=AsyncMock,
            return_value="https://signed.example.com/file",
        ) as mock_sign:
            result = await backend.sign_download_url(
                "data/file.csv", expiration=600
            )

        assert result == "https://signed.example.com/file"
        mock_sign.assert_called_once()
        args, kwargs = mock_sign.call_args
        assert args == (store, "GET", "data/file.csv")
        assert kwargs["expires_in"] == timedelta(seconds=600)

    async def test_sign_download_url_returns_none_on_exception(self) -> None:
        from obstore.store import S3Store

        store = S3Store("test-bucket", skip_signature=True)
        backend = self._make_backend(store)

        with patch(
            "obstore.sign_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("signing failed"),
        ):
            result = await backend.sign_download_url("data/file.csv")

        assert result is None

    def test_display_name_known_protocol(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        backend = self._make_backend(store)
        assert backend.display_name == "In-memory"


@pytest.mark.skipif(not HAS_FSSPEC, reason="fsspec not installed")
class TestFsspecFilesystem:
    def _make_backend(
        self, store: Any, name: str = "my_fs"
    ) -> FsspecFilesystem:
        return FsspecFilesystem(store, VariableName(name))

    def test_list_entries(self) -> None:
        mock_store = MagicMock()
        files = [
            {
                "name": "file1.txt",
                "size": 100,
                "type": "file",
                "mtime": 1234567890.0,
            },
            {
                "name": "subdir",
                "size": 0,
                "type": "directory",
                "mtime": 1234567891.0,
            },
        ]
        mock_store.ls.return_value = files

        backend = self._make_backend(mock_store)
        result = backend.list_entries(prefix="some/path")

        mock_store.ls.assert_called_once_with(path="some/path", detail=True)
        assert result == snapshot(
            [
                StorageEntry(
                    path="file1.txt",
                    kind="file",
                    size=100,
                    last_modified=1234567890.0,
                    metadata={},
                    mime_type="text/plain",
                ),
                StorageEntry(
                    path="subdir",
                    kind="directory",
                    size=0,
                    last_modified=1234567891.0,
                    metadata={},
                    mime_type=None,
                ),
            ]
        )

    def test_list_entries_none_prefix_uses_empty_string(self) -> None:
        mock_store = MagicMock()
        mock_store.ls.return_value = []

        backend = self._make_backend(mock_store)
        backend.list_entries(prefix=None)

        mock_store.ls.assert_called_once_with(path="", detail=True)

    def test_list_entries_respects_limit(self) -> None:
        mock_store = MagicMock()
        files = [
            {
                "name": f"file{i}.txt",
                "size": i * 10,
                "type": "file",
                "mtime": None,
            }
            for i in range(10)
        ]
        mock_store.ls.return_value = files

        backend = self._make_backend(mock_store)
        result = backend.list_entries(prefix="", limit=3)

        assert result == snapshot(
            [
                StorageEntry(
                    path="file0.txt",
                    kind="file",
                    size=0,
                    last_modified=None,
                    metadata={},
                    mime_type="text/plain",
                ),
                StorageEntry(
                    path="file1.txt",
                    kind="file",
                    size=10,
                    last_modified=None,
                    metadata={},
                    mime_type="text/plain",
                ),
                StorageEntry(
                    path="file2.txt",
                    kind="file",
                    size=20,
                    last_modified=None,
                    metadata={},
                    mime_type="text/plain",
                ),
            ]
        )

    def test_list_entries_raises_on_non_list(self) -> None:
        mock_store = MagicMock()
        mock_store.ls.return_value = "not_a_list"

        backend = self._make_backend(mock_store)
        with pytest.raises(ValueError, match="Files is not a list"):
            backend.list_entries(prefix="")

    def test_list_entries_skips_non_dict_entries(self) -> None:
        mock_store = MagicMock()
        mock_store.ls.return_value = [
            {"name": "good.txt", "size": 10, "type": "file"},
            "bad_entry",
            {"name": "also_good.txt", "size": 20, "type": "file"},
        ]

        backend = self._make_backend(mock_store)
        result = backend.list_entries(prefix="")

        assert result == snapshot(
            [
                StorageEntry(
                    path="good.txt",
                    kind="file",
                    size=10,
                    last_modified=None,
                    metadata={},
                    mime_type="text/plain",
                ),
                StorageEntry(
                    path="also_good.txt",
                    kind="file",
                    size=20,
                    last_modified=None,
                    metadata={},
                    mime_type="text/plain",
                ),
            ]
        )

    def test_identify_kind(self) -> None:
        mock_store = MagicMock()
        backend = self._make_backend(mock_store)

        assert backend._identify_kind("file") == "file"
        assert backend._identify_kind("FILE") == "file"
        assert backend._identify_kind("  file  ") == "file"
        assert backend._identify_kind("directory") == "directory"
        assert backend._identify_kind("DIRECTORY") == "directory"
        assert backend._identify_kind("  directory  ") == "directory"
        # Unknown types default to "file"
        assert backend._identify_kind("unknown") == "file"
        assert backend._identify_kind("symlink") == "file"

    def test_create_storage_entry_full(self) -> None:
        mock_store = MagicMock()
        backend = self._make_backend(mock_store)

        entry = backend._create_storage_entry(
            {
                "name": "data.csv",
                "size": 1024,
                "type": "file",
                "mtime": 1700000000.0,
                "ETag": "abc123",
                "islink": False,
                "mode": 0o644,
                "nlink": 1,
                "created": 1699000000.0,
            }
        )
        assert entry == snapshot(
            StorageEntry(
                path="data.csv",
                kind="file",
                size=1024,
                last_modified=1700000000.0,
                metadata={
                    "e_tag": "abc123",
                    "is_link": False,
                    "mode": 420,
                    "n_link": 1,
                    "created": 1699000000.0,
                },
                mime_type="text/csv",
            )
        )

    def test_create_storage_entry_missing_fields(self) -> None:
        mock_store = MagicMock()
        backend = self._make_backend(mock_store)

        entry = backend._create_storage_entry(
            {"name": None, "size": None, "type": None}
        )
        assert entry == snapshot(
            StorageEntry(
                path="",
                kind="file",
                size=0,
                last_modified=None,
                metadata={},
                mime_type=None,
            )
        )

    def test_create_storage_entry_directory(self) -> None:
        mock_store = MagicMock()
        backend = self._make_backend(mock_store)

        entry = backend._create_storage_entry(
            {"name": "my_dir/", "size": 0, "type": "directory", "mtime": None}
        )
        assert entry == snapshot(
            StorageEntry(
                path="my_dir/",
                kind="directory",
                size=0,
                last_modified=None,
                metadata={},
                mime_type=None,
            )
        )

    async def test_get_entry(self) -> None:
        mock_store = MagicMock()
        mock_store.info.return_value = {
            "name": "test.txt",
            "size": 42,
            "type": "file",
            "mtime": 1700000000.0,
        }

        backend = self._make_backend(mock_store)
        result = await backend.get_entry("test.txt")
        assert result == snapshot(
            StorageEntry(
                path="test.txt",
                kind="file",
                size=42,
                last_modified=1700000000.0,
                metadata={},
                mime_type="text/plain",
            )
        )

    async def test_get_entry_raises_on_non_dict(self) -> None:
        mock_store = MagicMock()
        mock_store.info.return_value = "not_a_dict"

        backend = self._make_backend(mock_store)
        with pytest.raises(ValueError, match="is not a dictionary"):
            await backend.get_entry("test.txt")

    async def test_download_bytes(self) -> None:
        mock_store = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = b"binary content"
        mock_store.open.return_value = mock_file

        backend = self._make_backend(mock_store)
        result = await backend.download("path/to/file.bin")
        assert result == b"binary content"
        mock_store.open.assert_called_once_with("path/to/file.bin")

    async def test_download_string_encoded_to_bytes(self) -> None:
        mock_store = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = "text content"
        mock_store.open.return_value = mock_file

        backend = self._make_backend(mock_store)
        result = await backend.download("path/to/file.txt")
        assert result == b"text content"

    async def test_download_file(self) -> None:
        mock_store = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = b"csv data"
        mock_store.open.return_value = mock_file

        backend = self._make_backend(mock_store)
        result = await backend.download_file("bucket/export.csv")

        assert result == DownloadResult(
            file_bytes=b"csv data",
            filename="export.csv",
            ext="csv",
        )

    async def test_read_range_returns_bytes(self) -> None:
        mock_store = MagicMock()
        mock_store.cat_file.return_value = b"partial content"

        backend = self._make_backend(mock_store)
        result = await backend.read_range("path/file.txt", offset=0, length=15)
        assert result == b"partial content"
        mock_store.cat_file.assert_called_once_with(
            "path/file.txt", start=0, end=15
        )

    async def test_read_range_encodes_string_to_bytes(self) -> None:
        mock_store = MagicMock()
        mock_store.cat_file.return_value = "text content"

        backend = self._make_backend(mock_store)
        result = await backend.read_range("path/file.txt", offset=0, length=50)
        assert result == b"text content"

    async def test_read_range_with_offset(self) -> None:
        mock_store = MagicMock()
        mock_store.cat_file.return_value = b"middle"

        backend = self._make_backend(mock_store)
        result = await backend.read_range("path/file.txt", offset=10, length=6)
        assert result == b"middle"
        mock_store.cat_file.assert_called_once_with(
            "path/file.txt", start=10, end=16
        )

    async def test_read_range_full_file(self) -> None:
        mock_store = MagicMock()
        mock_store.cat_file.return_value = b"entire file"

        backend = self._make_backend(mock_store)
        result = await backend.read_range("path/file.txt")
        assert result == b"entire file"
        mock_store.cat_file.assert_called_once_with(
            "path/file.txt", start=0, end=None
        )

    def test_protocol_tuple(self) -> None:
        mock_store = MagicMock()
        mock_store.protocol = ("gcs", "gs")

        backend = self._make_backend(mock_store)
        assert backend.protocol == "gcs"

    def test_root_path(self) -> None:
        mock_store = MagicMock()
        mock_store.root_marker = "/some/root"

        backend = self._make_backend(mock_store)
        assert backend.root_path == "/some/root"

    def test_root_path_empty(self) -> None:
        mock_store = MagicMock()
        mock_store.root_marker = ""

        backend = self._make_backend(mock_store)
        assert backend.root_path == ""

    def test_is_compatible_with_fsspec(self) -> None:
        from fsspec import AbstractFileSystem

        mock_fs = MagicMock(spec=AbstractFileSystem)
        assert FsspecFilesystem.is_compatible(mock_fs) is True

    def test_is_compatible_with_non_fsspec(self) -> None:
        assert FsspecFilesystem.is_compatible("not a fs") is False
        assert FsspecFilesystem.is_compatible(42) is False
        assert FsspecFilesystem.is_compatible(None) is False

    def test_is_compatible_with_concrete_filesystem(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        assert FsspecFilesystem.is_compatible(fs) is True

    def test_display_name_known_protocol(self) -> None:
        mock_store = MagicMock()
        mock_store.protocol = "s3"
        backend = self._make_backend(mock_store)
        assert backend.display_name == "Amazon S3"

    async def test_sign_download_url_returns_signed_url(self) -> None:
        mock_store = MagicMock()
        mock_store.sign.return_value = "https://signed.example.com/path"

        backend = self._make_backend(mock_store)
        result = await backend.sign_download_url(
            "bucket/file.csv", expiration=900
        )

        assert result == "https://signed.example.com/path"
        mock_store.sign.assert_called_once_with(
            "bucket/file.csv", expiration=900
        )

    async def test_sign_download_url_returns_none_on_not_implemented(
        self,
    ) -> None:
        mock_store = MagicMock()
        mock_store.sign.side_effect = NotImplementedError

        backend = self._make_backend(mock_store)
        result = await backend.sign_download_url("bucket/file.csv")

        assert result is None

    async def test_sign_download_url_returns_none_on_exception(self) -> None:
        mock_store = MagicMock()
        mock_store.sign.side_effect = RuntimeError("unexpected error")

        backend = self._make_backend(mock_store)
        result = await backend.sign_download_url("bucket/file.csv")

        assert result is None

    async def test_sign_download_url_converts_result_to_str(self) -> None:
        mock_store = MagicMock()
        mock_store.sign.return_value = 12345

        backend = self._make_backend(mock_store)
        result = await backend.sign_download_url("path")

        assert result == "12345"

    def test_display_name_unknown_protocol(self) -> None:
        mock_store = MagicMock()
        mock_store.protocol = "custom-proto"
        backend = self._make_backend(mock_store)
        assert backend.display_name == "Custom-proto"


@pytest.mark.skipif(not HAS_FSSPEC, reason="fsspec not installed")
class TestFsspecFilesystemIntegration:
    """Integration tests using a real fsspec MemoryFileSystem."""

    async def test_list_and_download_with_memory_fs(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.mkdir("/test")
        fs.pipe("/test/hello.txt", b"hello world")
        fs.pipe("/test/data.csv", b"a,b,c\n1,2,3")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        entries = backend.list_entries(prefix="/test")

        assert entries == snapshot(
            [
                StorageEntry(
                    path="/test/hello.txt",
                    kind="file",
                    size=11,
                    last_modified=None,
                    metadata={"created": IsPositiveFloat()},
                    mime_type="text/plain",
                ),
                StorageEntry(
                    path="/test/data.csv",
                    kind="file",
                    size=11,
                    last_modified=None,
                    metadata={"created": IsPositiveFloat()},
                    mime_type="text/csv",
                ),
            ]
        )

        result = await backend.download("/test/hello.txt")
        assert result == b"hello world"

    async def test_get_entry_with_memory_fs(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.pipe("/myfile.txt", b"content here")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        entry = await backend.get_entry("/myfile.txt")
        assert entry == snapshot(
            StorageEntry(
                path="/myfile.txt",
                kind="file",
                size=12,
                last_modified=None,
                metadata={"created": IsDatetime()},
                mime_type="text/plain",
            )
        )

    async def test_sign_download_url_not_implemented_by_memory_fs(
        self,
    ) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.pipe("/test/file.txt", b"hello")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        result = await backend.sign_download_url("/test/file.txt")
        assert result is None

    async def test_read_range_full_file(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.pipe("/test/data.txt", b"hello world")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        result = await backend.read_range("/test/data.txt")
        assert result == b"hello world"

    async def test_read_range_partial(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.pipe("/test/data.txt", b"hello world")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        result = await backend.read_range("/test/data.txt", offset=0, length=5)
        assert result == b"hello"

    async def test_read_range_with_offset(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.pipe("/test/data.txt", b"hello world")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        result = await backend.read_range("/test/data.txt", offset=6, length=5)
        assert result == b"world"

    async def test_read_range_offset_without_length(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.pipe("/test/data.txt", b"hello world")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        result = await backend.read_range("/test/data.txt", offset=6)
        assert result == b"world"

    def test_protocol_memory_filesystem(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        # MemoryFileSystem protocol is "memory", which doesn't match known types
        assert backend.protocol == "memory"


@pytest.mark.skipif(not HAS_OBSTORE, reason="obstore not installed")
class TestObstoreIntegration:
    """Integration tests using a real obstore MemoryStore."""

    async def test_list_entries_with_memory_store(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        # Put some data
        await store.put_async("test/file1.txt", b"hello")
        await store.put_async("test/file2.txt", b"world!")

        backend = Obstore(store, VariableName("mem_store"))
        entries = backend.list_entries(prefix="test/")
        assert entries == snapshot(
            [
                StorageEntry(
                    path="test/file1.txt",
                    kind="object",
                    size=5,
                    last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                    metadata={"e_tag": "0"},
                    mime_type="text/plain",
                ),
                StorageEntry(
                    path="test/file2.txt",
                    kind="object",
                    size=6,
                    last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                    metadata={"e_tag": "1"},
                    mime_type="text/plain",
                ),
            ]
        )

    async def test_download_with_memory_store(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        await store.put_async("data.bin", b"binary data")

        backend = Obstore(store, VariableName("mem_store"))
        result = await backend.download("data.bin")
        assert result == b"binary data"

    async def test_get_entry_with_memory_store(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        await store.put_async("info.txt", b"some content")

        backend = Obstore(store, VariableName("mem_store"))
        entry = await backend.get_entry("info.txt")
        assert entry == snapshot(
            StorageEntry(
                path="info.txt",
                kind="object",
                size=12,
                last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                metadata={"e_tag": "0"},
                mime_type="text/plain",
            )
        )

    async def test_sign_download_url_returns_none_for_memory_store(
        self,
    ) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        await store.put_async("data.txt", b"test")

        backend = Obstore(store, VariableName("mem_store"))
        result = await backend.sign_download_url("data.txt")
        assert result is None

    async def test_read_range_full_file(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        await store.put_async("file.txt", b"hello world")

        backend = Obstore(store, VariableName("mem_store"))
        result = await backend.read_range("file.txt")
        assert result == b"hello world"

    async def test_read_range_partial(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        await store.put_async("file.txt", b"hello world")

        backend = Obstore(store, VariableName("mem_store"))
        result = await backend.read_range("file.txt", offset=0, length=5)
        assert result == b"hello"

    async def test_read_range_with_offset(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        await store.put_async("file.txt", b"hello world")

        backend = Obstore(store, VariableName("mem_store"))
        result = await backend.read_range("file.txt", offset=6, length=5)
        assert result == b"world"

    async def test_read_range_offset_without_length(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        await store.put_async("file.txt", b"hello world")

        backend = Obstore(store, VariableName("mem_store"))
        result = await backend.read_range("file.txt", offset=6)
        assert result == b"world"


class TestNormalizeProtocol:
    @pytest.mark.parametrize(
        ("protocol", "expected"),
        [
            ("s3", "s3"),
            ("s3a", "s3"),
            ("S3", "s3"),
            ("gcs", "gcs"),
            ("GCS", "gcs"),
            ("gs-gcs", "gcs"),
            ("azure", "azure"),
            ("Azure", "azure"),
            ("abfs-azure", "azure"),
            ("http", "http"),
            ("HTTP", "http"),
            ("https-http", "http"),
            ("file", "file"),
            ("FILE", "file"),
            ("local-file", "file"),
            ("ftp", "ftp"),
            ("custom", "custom"),
            ("  s3  ", "s3"),
            ("  gcs  ", "gcs"),
        ],
    )
    def test_normalize_protocol(self, protocol: str, expected: str) -> None:
        assert normalize_protocol(protocol) == expected


# --- Helpers ---


async def _async_return(value: Any) -> Any:
    return value
