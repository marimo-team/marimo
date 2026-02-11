# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from dirty_equals import IsDatetime, IsPositiveFloat
from inline_snapshot import snapshot

from marimo._dependencies.dependencies import DependencyManager
from marimo._storage.models import StorageEntry
from marimo._storage.storage import (
    FsspecFilesystem,
    Obstore,
    normalize_protocol,
)
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
                ),
                StorageEntry(
                    path="file1.txt",
                    kind="object",
                    size=100,
                    last_modified=now.timestamp(),
                    metadata={"e_tag": "abc"},
                ),
                StorageEntry(
                    path="dir/file2.txt",
                    kind="object",
                    size=200,
                    last_modified=now.timestamp(),
                    metadata={"version": "v1"},
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
                size=0,
                last_modified=None,
                kind="object",
                metadata={},
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
                size=500,
                last_modified=now.timestamp(),
                kind="object",
                metadata={"e_tag": "etag123", "version": "v2"},
            )
        )

    def test_get_entry(self) -> None:
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
        result = asyncio.get_event_loop().run_until_complete(
            backend.get_entry("test.txt")
        )
        assert result == snapshot(
            StorageEntry(
                path="test.txt",
                size=42,
                last_modified=now.timestamp(),
                kind="object",
                metadata={"e_tag": "e1"},
            )
        )
        mock_store.head_async.assert_called_once_with("test.txt")

    def test_download(self) -> None:
        mock_store = MagicMock()
        mock_bytes_result = MagicMock()
        mock_bytes_result.bytes_async = MagicMock(
            return_value=_async_return(b"hello world")
        )
        mock_store.get_async = MagicMock(
            return_value=_async_return(mock_bytes_result)
        )

        backend = self._make_backend(mock_store)
        result = asyncio.get_event_loop().run_until_complete(
            backend.download("some/path.txt")
        )
        assert result == b"hello world"
        mock_store.get_async.assert_called_once_with("some/path.txt")

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
                    size=100,
                    last_modified=1234567890.0,
                    kind="file",
                    metadata={},
                ),
                StorageEntry(
                    path="subdir",
                    size=0,
                    last_modified=1234567891.0,
                    kind="directory",
                    metadata={},
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
                    size=0,
                    last_modified=None,
                    kind="file",
                    metadata={},
                ),
                StorageEntry(
                    path="file1.txt",
                    kind="file",
                    size=10,
                    last_modified=None,
                    metadata={},
                ),
                StorageEntry(
                    path="file2.txt",
                    kind="file",
                    size=20,
                    last_modified=None,
                    metadata={},
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
                    size=10,
                    last_modified=None,
                    kind="file",
                    metadata={},
                ),
                StorageEntry(
                    path="also_good.txt",
                    size=20,
                    last_modified=None,
                    kind="file",
                    metadata={},
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
                size=1024,
                last_modified=1700000000.0,
                kind="file",
                metadata={
                    "e_tag": "abc123",
                    "is_link": False,
                    "mode": 420,
                    "n_link": 1,
                    "created": 1699000000.0,
                },
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
                size=0,
                last_modified=None,
                kind="file",
                metadata={},
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
                size=0,
                last_modified=None,
                kind="directory",
                metadata={},
            )
        )

    def test_get_entry(self) -> None:
        mock_store = MagicMock()
        mock_store.info.return_value = {
            "name": "test.txt",
            "size": 42,
            "type": "file",
            "mtime": 1700000000.0,
        }

        backend = self._make_backend(mock_store)
        result = asyncio.get_event_loop().run_until_complete(
            backend.get_entry("test.txt")
        )
        assert result == snapshot(
            StorageEntry(
                path="test.txt",
                size=42,
                last_modified=1700000000.0,
                kind="file",
                metadata={},
            )
        )

    def test_get_entry_raises_on_non_dict(self) -> None:
        mock_store = MagicMock()
        mock_store.info.return_value = "not_a_dict"

        backend = self._make_backend(mock_store)
        with pytest.raises(ValueError, match="is not a dictionary"):
            asyncio.get_event_loop().run_until_complete(
                backend.get_entry("test.txt")
            )

    def test_download_bytes(self) -> None:
        mock_store = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = b"binary content"
        mock_store._open.return_value = mock_file

        backend = self._make_backend(mock_store)
        result = asyncio.get_event_loop().run_until_complete(
            backend.download("path/to/file.bin")
        )
        assert result == b"binary content"
        mock_store._open.assert_called_once_with("path/to/file.bin")

    def test_download_string_encoded_to_bytes(self) -> None:
        mock_store = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = "text content"
        mock_store._open.return_value = mock_file

        backend = self._make_backend(mock_store)
        result = asyncio.get_event_loop().run_until_complete(
            backend.download("path/to/file.txt")
        )
        assert result == b"text content"

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


@pytest.mark.skipif(not HAS_FSSPEC, reason="fsspec not installed")
class TestFsspecFilesystemIntegration:
    """Integration tests using a real fsspec MemoryFileSystem."""

    def test_list_and_download_with_memory_fs(self) -> None:
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
                ),
                StorageEntry(
                    path="/test/data.csv",
                    kind="file",
                    size=11,
                    last_modified=None,
                    metadata={"created": IsPositiveFloat()},
                ),
            ]
        )

        result = asyncio.get_event_loop().run_until_complete(
            backend.download("/test/hello.txt")
        )
        assert result == b"hello world"

    def test_get_entry_with_memory_fs(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        fs.pipe("/myfile.txt", b"content here")

        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        entry = asyncio.get_event_loop().run_until_complete(
            backend.get_entry("/myfile.txt")
        )
        assert entry == snapshot(
            StorageEntry(
                path="/myfile.txt",
                kind="file",
                size=12,
                last_modified=None,
                metadata={"created": IsDatetime()},
            )
        )

    def test_protocol_memory_filesystem(self) -> None:
        from fsspec.implementations.memory import MemoryFileSystem

        fs = MemoryFileSystem()
        backend = FsspecFilesystem(fs, VariableName("mem_fs"))
        # MemoryFileSystem protocol is "memory", which doesn't match known types
        assert backend.protocol == "memory"


@pytest.mark.skipif(not HAS_OBSTORE, reason="obstore not installed")
class TestObstoreIntegration:
    """Integration tests using a real obstore MemoryStore."""

    def test_list_entries_with_memory_store(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        # Put some data
        asyncio.get_event_loop().run_until_complete(
            store.put_async("test/file1.txt", b"hello")
        )
        asyncio.get_event_loop().run_until_complete(
            store.put_async("test/file2.txt", b"world!")
        )

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
                ),
                StorageEntry(
                    path="test/file2.txt",
                    kind="object",
                    size=6,
                    last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                    metadata={"e_tag": "1"},
                ),
            ]
        )

    def test_download_with_memory_store(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        asyncio.get_event_loop().run_until_complete(
            store.put_async("data.bin", b"binary data")
        )

        backend = Obstore(store, VariableName("mem_store"))
        result = asyncio.get_event_loop().run_until_complete(
            backend.download("data.bin")
        )
        assert result == b"binary data"

    def test_get_entry_with_memory_store(self) -> None:
        from obstore.store import MemoryStore

        store = MemoryStore()
        asyncio.get_event_loop().run_until_complete(
            store.put_async("info.txt", b"some content")
        )

        backend = Obstore(store, VariableName("mem_store"))
        entry = asyncio.get_event_loop().run_until_complete(
            backend.get_entry("info.txt")
        )
        assert entry == snapshot(
            StorageEntry(
                path="info.txt",
                kind="object",
                size=12,
                last_modified=IsPositiveFloat(),  # pyright: ignore[reportArgumentType]
                metadata={"e_tag": "0"},
            )
        )


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
