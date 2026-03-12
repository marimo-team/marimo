# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._runtime.virtual_file.storage import (
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
