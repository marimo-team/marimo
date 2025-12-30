# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

import pytest

from marimo._runtime.virtual_file.storage import (
    InMemoryStorage,
    SharedMemoryStorage,
    VirtualFileStorageManager,
)
from marimo._utils.platform import is_pyodide


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


@pytest.mark.skipif(is_pyodide(), reason="SharedMemory not supported on Pyodide")
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

    @pytest.mark.skipif(
        is_pyodide(), reason="SharedMemory not supported on Pyodide"
    )
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
