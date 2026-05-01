# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._runtime.virtual_file.storage import (
    DiskStorage,
    FallbackStorage,
    InMemoryStorage,
    SharedMemoryStorage,
    VirtualFileStorageManager,
)


class TestInMemoryStorageReadChunked:
    def test_read_chunked_basic(self) -> None:
        storage = InMemoryStorage()
        storage.store("test_key", b"hello world")
        chunks = list(storage.read_chunked("test_key", 11))
        assert b"".join(chunks) == b"hello world"

    def test_read_chunked_with_byte_length(self) -> None:
        storage = InMemoryStorage()
        storage.store("test_key", b"hello world")
        chunks = list(storage.read_chunked("test_key", 5))
        assert b"".join(chunks) == b"hello"

    def test_read_chunked_multiple_chunks(self) -> None:
        storage = InMemoryStorage()
        data = b"a" * 100
        storage.store("test_key", data)
        # Use a small chunk size to force multiple chunks
        chunks = list(storage.read_chunked("test_key", 100, chunk_size=30))
        assert b"".join(chunks) == data
        assert len(chunks) == 4  # 30 + 30 + 30 + 10

    def test_read_chunked_nonexistent_raises_keyerror(self) -> None:
        storage = InMemoryStorage()
        with pytest.raises(KeyError, match="Virtual file not found"):
            list(storage.read_chunked("nonexistent", 10))

    def test_read_chunked_chunk_sizes(self) -> None:
        """Verify each chunk is at most chunk_size bytes."""
        storage = InMemoryStorage()
        data = b"x" * 250
        storage.store("test_key", data)
        chunk_size = 64
        chunks = list(
            storage.read_chunked("test_key", 250, chunk_size=chunk_size)
        )
        for chunk in chunks[:-1]:
            assert len(chunk) == chunk_size
        # Last chunk may be smaller
        assert len(chunks[-1]) <= chunk_size
        assert b"".join(chunks) == data


class TestInMemoryStorage:
    def test_store_and_read(self) -> None:
        storage = InMemoryStorage()
        storage.store("test_key", b"hello world")
        result = storage.read("test_key", 11)
        assert result == b"hello world"

    def test_read_with_byte_length(self) -> None:
        storage = InMemoryStorage()
        storage.store("test_key", b"hello world")
        result = storage.read("test_key", 5)
        assert result == b"hello"

    def test_read_nonexistent_raises_keyerror(self) -> None:
        storage = InMemoryStorage()
        with pytest.raises(KeyError, match="Virtual file not found"):
            storage.read("nonexistent", 10)

    def test_store_overwrites(self) -> None:
        storage = InMemoryStorage()
        storage.store("test_key", b"original")
        storage.store("test_key", b"updated")
        result = storage.read("test_key", 7)
        assert result == b"updated"

    def test_remove(self) -> None:
        storage = InMemoryStorage()
        storage.store("test_key", b"hello")
        assert storage.has("test_key")
        storage.remove("test_key")
        assert not storage.has("test_key")

    def test_remove_nonexistent_no_error(self) -> None:
        storage = InMemoryStorage()
        storage.remove("nonexistent")  # Should not raise

    def test_has(self) -> None:
        storage = InMemoryStorage()
        assert not storage.has("test_key")
        storage.store("test_key", b"hello")
        assert storage.has("test_key")

    def test_shutdown_clears_storage(self) -> None:
        storage = InMemoryStorage()
        storage.store("key1", b"data1")
        storage.store("key2", b"data2")
        assert storage.has("key1")
        assert storage.has("key2")
        storage.shutdown()
        assert not storage.has("key1")
        assert not storage.has("key2")


class TestSharedMemoryStorage:
    def test_store_and_read(self) -> None:
        storage = SharedMemoryStorage()
        try:
            storage.store("marimo_test_1", b"hello world")
            result = storage.read("marimo_test_1", 11)
            assert result == b"hello world"
        finally:
            storage.shutdown()

    def test_read_with_byte_length(self) -> None:
        storage = SharedMemoryStorage()
        try:
            storage.store("marimo_test_2", b"hello world")
            result = storage.read("marimo_test_2", 5)
            assert result == b"hello"
        finally:
            storage.shutdown()

    def test_read_nonexistent_raises_keyerror(self) -> None:
        storage = SharedMemoryStorage()
        try:
            with pytest.raises(KeyError, match="Virtual file not found"):
                storage.read("nonexistent_key_xyz", 10)
        finally:
            storage.shutdown()

    def test_store_duplicate_skipped(self) -> None:
        storage = SharedMemoryStorage()
        try:
            storage.store("marimo_test_3", b"original")
            # Second store should be a no-op (not overwrite)
            storage.store("marimo_test_3", b"updated_longer")
            result = storage.read("marimo_test_3", 8)
            assert result == b"original"
        finally:
            storage.shutdown()

    def test_remove(self) -> None:
        storage = SharedMemoryStorage()
        try:
            storage.store("marimo_test_4", b"hello")
            assert storage.has("marimo_test_4")
            storage.remove("marimo_test_4")
            assert not storage.has("marimo_test_4")
        finally:
            storage.shutdown()

    def test_remove_nonexistent_no_error(self) -> None:
        storage = SharedMemoryStorage()
        try:
            storage.remove("nonexistent")  # Should not raise
        finally:
            storage.shutdown()

    def test_has(self) -> None:
        storage = SharedMemoryStorage()
        try:
            assert not storage.has("marimo_test_5")
            storage.store("marimo_test_5", b"hello")
            assert storage.has("marimo_test_5")
        finally:
            storage.shutdown()

    def test_shutdown_clears_storage(self) -> None:
        storage = SharedMemoryStorage()
        storage.store("marimo_test_6", b"data1")
        storage.store("marimo_test_7", b"data2")
        assert storage.has("marimo_test_6")
        assert storage.has("marimo_test_7")
        storage.shutdown()
        assert not storage.has("marimo_test_6")
        assert not storage.has("marimo_test_7")

    def test_shutdown_with_keys_only_removes_requested_entries(self) -> None:
        storage = SharedMemoryStorage()
        try:
            storage.store("marimo_test_subset_1", b"data1")
            storage.store("marimo_test_subset_2", b"data2")

            storage.shutdown(keys=["marimo_test_subset_1"])

            assert not storage.has("marimo_test_subset_1")
            assert storage.has("marimo_test_subset_2")
            assert storage.read("marimo_test_subset_2", 5) == b"data2"
        finally:
            storage.shutdown()

    def test_cross_process_read(self) -> None:
        """Test that shared memory can be read by name from a fresh instance."""
        storage1 = SharedMemoryStorage()
        try:
            storage1.store("marimo_test_cross", b"cross process data")
            # Create a new instance and read by name
            storage2 = SharedMemoryStorage()
            result = storage2.read("marimo_test_cross", 18)
            assert result == b"cross process data"
        finally:
            storage1.shutdown()

    def test_shutdown_is_reentrant(self) -> None:
        """Test that shutdown can be called multiple times safely."""
        storage = SharedMemoryStorage()
        storage.store("marimo_test_8", b"data")
        storage.shutdown()
        storage.shutdown()  # Should not raise

    def test_read_chunked_basic(self) -> None:
        storage = SharedMemoryStorage()
        try:
            storage.store("marimo_chunk_1", b"hello world")
            chunks = list(storage.read_chunked("marimo_chunk_1", 11))
            assert b"".join(chunks) == b"hello world"
        finally:
            storage.shutdown()

    def test_read_chunked_with_byte_length(self) -> None:
        storage = SharedMemoryStorage()
        try:
            storage.store("marimo_chunk_2", b"hello world")
            chunks = list(storage.read_chunked("marimo_chunk_2", 5))
            assert b"".join(chunks) == b"hello"
        finally:
            storage.shutdown()

    def test_read_chunked_multiple_chunks(self) -> None:
        storage = SharedMemoryStorage()
        try:
            data = b"a" * 100
            storage.store("marimo_chunk_3", data)
            chunks = list(
                storage.read_chunked("marimo_chunk_3", 100, chunk_size=30)
            )
            assert b"".join(chunks) == data
            assert len(chunks) == 4  # 30 + 30 + 30 + 10
        finally:
            storage.shutdown()

    def test_read_chunked_nonexistent_raises_keyerror(self) -> None:
        storage = SharedMemoryStorage()
        try:
            with pytest.raises(KeyError, match="Virtual file not found"):
                list(storage.read_chunked("nonexistent_chunk", 10))
        finally:
            storage.shutdown()

    def test_read_chunked_cross_process(self) -> None:
        """Test chunked read works across fresh instances."""
        storage1 = SharedMemoryStorage()
        try:
            data = b"cross process chunked"
            storage1.store("marimo_chunk_cross", data)
            storage2 = SharedMemoryStorage()
            chunks = list(
                storage2.read_chunked(
                    "marimo_chunk_cross", len(data), chunk_size=5
                )
            )
            assert b"".join(chunks) == data
        finally:
            storage1.shutdown()

    def test_read_chunked_data_integrity(self) -> None:
        """Test that chunked read produces identical data to regular read."""
        storage = SharedMemoryStorage()
        try:
            data = bytes(range(256)) * 4  # 1024 bytes of varied data
            storage.store("marimo_chunk_integ", data)
            regular = storage.read("marimo_chunk_integ", len(data))
            chunked = b"".join(
                storage.read_chunked(
                    "marimo_chunk_integ", len(data), chunk_size=100
                )
            )
            assert regular == chunked == data
        finally:
            storage.shutdown()


class TestDiskStorage:
    @pytest.fixture
    def storage(self, tmp_path) -> DiskStorage:
        return DiskStorage(base_dir=tmp_path)

    def test_store_and_read(self, storage: DiskStorage) -> None:
        storage.store("k", b"hello world")
        assert storage.read("k", 11) == b"hello world"

    def test_read_with_byte_length(self, storage: DiskStorage) -> None:
        storage.store("k", b"hello world")
        assert storage.read("k", 5) == b"hello"

    def test_read_nonexistent_raises_keyerror(
        self, storage: DiskStorage
    ) -> None:
        with pytest.raises(KeyError, match="Virtual file not found"):
            storage.read("missing", 10)

    def test_read_chunked(self, storage: DiskStorage) -> None:
        data = b"a" * 100
        storage.store("k", data)
        chunks = list(storage.read_chunked("k", 100, chunk_size=30))
        assert b"".join(chunks) == data
        assert len(chunks) == 4

    def test_read_chunked_with_byte_length(self, storage: DiskStorage) -> None:
        storage.store("k", b"hello world")
        chunks = list(storage.read_chunked("k", 5))
        assert b"".join(chunks) == b"hello"

    def test_read_chunked_nonexistent_raises_keyerror(
        self, storage: DiskStorage
    ) -> None:
        with pytest.raises(KeyError, match="Virtual file not found"):
            list(storage.read_chunked("missing", 10))

    def test_remove(self, storage: DiskStorage) -> None:
        storage.store("k", b"hi")
        assert storage.has("k")
        storage.remove("k")
        assert not storage.has("k")

    def test_remove_nonexistent_no_error(self, storage: DiskStorage) -> None:
        storage.remove("missing")

    def test_has(self, storage: DiskStorage) -> None:
        assert not storage.has("k")
        storage.store("k", b"hi")
        assert storage.has("k")

    def test_shutdown_only_removes_owned_keys(self, tmp_path) -> None:
        # Two instances share a directory; shutdown of one must not nuke the
        # other's files (mirrors the cross-process kernel/server scenario).
        a = DiskStorage(base_dir=tmp_path)
        b = DiskStorage(base_dir=tmp_path)
        a.store("ak", b"a-data")
        b.store("bk", b"b-data")
        a.shutdown()
        assert not (tmp_path / "ak").exists()
        assert (tmp_path / "bk").exists()
        b.shutdown()

    def test_shutdown_with_keys(self, storage: DiskStorage) -> None:
        storage.store("k1", b"d1")
        storage.store("k2", b"d2")
        storage.shutdown(keys=["k1"])
        assert not storage.has("k1")
        assert storage.has("k2")
        assert not storage.stale  # only full shutdown sets stale

    def test_shutdown_full_marks_stale(self, storage: DiskStorage) -> None:
        assert not storage.stale
        storage.shutdown()
        assert storage.stale

    def test_cross_process_read_via_path(self, tmp_path) -> None:
        # A second instance pointing at the same dir can read what the first
        # wrote — the foundation of cross-process serving.
        writer = DiskStorage(base_dir=tmp_path)
        writer.store("shared", b"shared bytes")
        reader = DiskStorage(base_dir=tmp_path)
        assert reader.read("shared", 12) == b"shared bytes"
        writer.shutdown()


class _RaisingStorage(InMemoryStorage):
    """Test double: raises OSError on store, otherwise behaves normally."""

    def __init__(self, errno: int = 28) -> None:
        super().__init__()
        self._errno = errno
        self.store_calls = 0

    def store(self, key: str, buffer: bytes) -> None:  # noqa: ARG002
        self.store_calls += 1
        raise OSError(self._errno, "No space left on device")


class TestFallbackStorage:
    def test_requires_at_least_one_backend(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            FallbackStorage([])

    def test_uses_first_backend_when_healthy(self) -> None:
        primary = InMemoryStorage()
        secondary = InMemoryStorage()
        fb = FallbackStorage([primary, secondary])
        fb.store("k", b"data")
        assert primary.has("k")
        assert not secondary.has("k")
        assert fb.read("k", 4) == b"data"

    def test_falls_back_on_oserror(self) -> None:
        primary = _RaisingStorage()
        secondary = InMemoryStorage()
        fb = FallbackStorage([primary, secondary])
        fb.store("k", b"data")
        assert primary.store_calls == 1
        assert secondary.has("k")
        assert fb.read("k", 4) == b"data"

    def test_reraises_when_all_backends_fail(self) -> None:
        a = _RaisingStorage(errno=28)
        b = _RaisingStorage(errno=12)
        fb = FallbackStorage([a, b])
        with pytest.raises(OSError) as exc:
            fb.store("k", b"data")
        # Last error is propagated
        assert exc.value.errno == 12

    def test_routing_directs_reads_and_removes(self) -> None:
        primary = _RaisingStorage()
        secondary = InMemoryStorage()
        fb = FallbackStorage([primary, secondary])
        fb.store("k", b"hello")
        assert fb.has("k")
        assert b"".join(fb.read_chunked("k", 5, chunk_size=2)) == b"hello"
        fb.remove("k")
        assert not fb.has("k")
        assert not secondary.has("k")

    def test_probe_path_for_unrouted_keys(self, tmp_path) -> None:
        # Mirrors the cross-process reader scenario: write via one instance,
        # read via a fresh FallbackStorage that has no routing entry.
        writer = DiskStorage(base_dir=tmp_path)
        writer.store("shared", b"shared bytes")
        reader = FallbackStorage(
            [InMemoryStorage(), DiskStorage(base_dir=tmp_path)]
        )
        assert reader.has("shared")
        assert reader.read("shared", 12) == b"shared bytes"
        chunks = list(reader.read_chunked("shared", 12, chunk_size=4))
        assert b"".join(chunks) == b"shared bytes"
        writer.shutdown()

    def test_read_missing_raises_keyerror(self) -> None:
        fb = FallbackStorage([InMemoryStorage(), InMemoryStorage()])
        with pytest.raises(KeyError, match="Virtual file not found"):
            fb.read("missing", 10)
        with pytest.raises(KeyError, match="Virtual file not found"):
            list(fb.read_chunked("missing", 10))

    def test_skips_stale_backends(self, tmp_path) -> None:
        stale_disk = DiskStorage(base_dir=tmp_path)
        stale_disk.shutdown()  # marks _stale = True
        assert stale_disk.stale
        ok = InMemoryStorage()
        fb = FallbackStorage([stale_disk, ok])
        fb.store("k", b"hi")
        assert ok.has("k")

    def test_shutdown_propagates_to_all_backends(self) -> None:
        a = InMemoryStorage()
        b = InMemoryStorage()
        fb = FallbackStorage([a, b])
        fb.store("k1", b"d1")
        # Manually populate b to simulate independent state
        b.store("k2", b"d2")
        fb.shutdown()
        assert not a.has("k1")
        assert not b.has("k2")

    def test_shutdown_with_keys_propagates(self) -> None:
        a = InMemoryStorage()
        b = InMemoryStorage()
        fb = FallbackStorage([a, b])
        fb.store("k1", b"d1")
        b.store("k2", b"d2")
        fb.shutdown(keys=["k1", "k2"])
        assert not a.has("k1")
        assert not b.has("k2")

    def test_stale_iff_all_backends_stale(self, tmp_path) -> None:
        a = DiskStorage(base_dir=str(tmp_path / "a"))
        b = DiskStorage(base_dir=str(tmp_path / "b"))
        fb = FallbackStorage([a, b])
        assert not fb.stale
        a.shutdown()
        assert not fb.stale
        b.shutdown()
        assert fb.stale


class TestVirtualFileStorageManager:
    def test_singleton(self) -> None:
        manager1 = VirtualFileStorageManager()
        manager2 = VirtualFileStorageManager()
        assert manager1 is manager2

    def test_storage_property(self) -> None:
        manager = VirtualFileStorageManager()
        original_storage = manager.storage
        try:
            storage = InMemoryStorage()
            manager.storage = storage
            assert manager.storage is storage
        finally:
            manager.storage = original_storage

    def test_read_with_storage(self) -> None:
        manager = VirtualFileStorageManager()
        original_storage = manager.storage
        try:
            storage = InMemoryStorage()
            storage.store("test_file", b"test data")
            manager.storage = storage
            result = manager.read("test_file", 9)
            assert result == b"test data"
        finally:
            manager.storage = original_storage

    def test_read_without_storage_falls_back_to_shared_memory(self) -> None:
        manager = VirtualFileStorageManager()
        original_storage = manager.storage
        # Store data in shared memory directly
        shm_storage = SharedMemoryStorage()
        try:
            shm_storage.store("marimo_fallback_test", b"fallback data")
            # Set manager storage to None to trigger fallback
            manager.storage = None
            result = manager.read("marimo_fallback_test", 13)
            assert result == b"fallback data"
        finally:
            manager.storage = original_storage
            shm_storage.shutdown()

    def test_read_chunked_with_storage(self) -> None:
        manager = VirtualFileStorageManager()
        original_storage = manager.storage
        try:
            storage = InMemoryStorage()
            storage.store("test_file", b"test data chunked")
            manager.storage = storage
            chunks = list(manager.read_chunked("test_file", 17))
            assert b"".join(chunks) == b"test data chunked"
        finally:
            manager.storage = original_storage

    def test_read_chunked_falls_back_to_shared_memory(self) -> None:
        manager = VirtualFileStorageManager()
        original_storage = manager.storage
        shm_storage = SharedMemoryStorage()
        try:
            shm_storage.store("marimo_fb_chunk", b"fallback chunked")
            manager.storage = None
            chunks = list(
                manager.read_chunked("marimo_fb_chunk", 16, chunk_size=4)
            )
            assert b"".join(chunks) == b"fallback chunked"
            assert len(chunks) == 4  # 16 / 4 = 4 chunks
        finally:
            manager.storage = original_storage
            shm_storage.shutdown()
