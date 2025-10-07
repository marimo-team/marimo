# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

import pytest

from marimo._save.stores import MemoryStore


class TestMemoryStore:
    def test_put_and_get(self) -> None:
        """Test basic put and get operations."""
        store = MemoryStore()
        key = "test_key"
        value = b"test_value"

        assert store.put(key, value)
        assert store.get(key) == value

        store.clear_all()

    def test_get_missing_key(self) -> None:
        """Test that getting a missing key returns None."""
        store = MemoryStore()
        assert store.get("nonexistent") is None
        store.clear_all()

    def test_hit_existing_key(self) -> None:
        """Test hit returns True for existing keys."""
        store = MemoryStore()
        key = "test_key"
        value = b"test_value"

        store.put(key, value)
        assert store.hit(key) is True

        store.clear_all()

    def test_hit_missing_key(self) -> None:
        """Test hit returns False for missing keys."""
        store = MemoryStore()
        assert store.hit("nonexistent") is False

    def test_clear_existing_key(self) -> None:
        """Test clearing an existing key."""
        store = MemoryStore()
        key = "test_key"
        value = b"test_value"

        store.put(key, value)
        assert store.hit(key) is True

        assert store.clear(key) is True
        assert store.hit(key) is False
        assert store.get(key) is None

    def test_clear_missing_key(self) -> None:
        """Test clearing a missing key returns False."""
        store = MemoryStore()
        assert store.clear("nonexistent") is False

    def test_overwrite_existing_key(self) -> None:
        """Test that putting to an existing key overwrites the value."""
        store = MemoryStore()
        key = "test_key"
        value1 = b"first_value"
        value2 = b"second_value"

        store.put(key, value1)
        assert store.get(key) == value1

        store.put(key, value2)
        assert store.get(key) == value2

        store.clear_all()

    def test_multiple_keys(self) -> None:
        """Test storing multiple keys simultaneously."""
        store = MemoryStore()
        data = {
            "key1": b"value1",
            "key2": b"value2",
            "key3": b"value3",
        }

        for key, value in data.items():
            store.put(key, value)

        for key, value in data.items():
            assert store.get(key) == value
            assert store.hit(key) is True

        store.clear_all()

    def test_large_data(self) -> None:
        """Test storing large data values."""
        store = MemoryStore()
        key = "large_key"
        # 10 MB of data
        value = b"x" * (10 * 1024 * 1024)

        assert store.put(key, value)
        assert store.get(key) == value

        store.clear_all()

    def test_empty_value(self) -> None:
        """Test storing empty byte strings."""
        store = MemoryStore()
        key = "empty_key"
        value = b""

        assert store.put(key, value)
        assert store.get(key) == value
        assert store.hit(key) is True

        store.clear_all()

    def test_clear_all(self) -> None:
        """Test clearing all stored data."""
        store = MemoryStore()
        data = {
            "key1": b"value1",
            "key2": b"value2",
            "key3": b"value3",
        }

        for key, value in data.items():
            store.put(key, value)

        store.clear_all()

        for key in data.keys():
            assert store.hit(key) is False
            assert store.get(key) is None

    def test_cleanup_on_deletion(self) -> None:
        """Test that shared memory is cleaned up when store is deleted."""
        store = MemoryStore()
        key = "test_key"
        value = b"test_value"

        store.put(key, value)
        shm_name = store._shm_name(key)

        # Delete the store
        del store

        # Try to access the shared memory - should fail
        from multiprocessing import shared_memory
        with pytest.raises(FileNotFoundError):
            shm = shared_memory.SharedMemory(name=shm_name)
            shm.close()

    def test_thread_safety(self) -> None:
        """Test that operations are thread-safe."""
        import threading

        store = MemoryStore()
        results = []

        def put_data(key: str, value: bytes) -> None:
            result = store.put(key, value)
            results.append(result)

        threads = []
        for i in range(10):
            key = f"key_{i}"
            value = f"value_{i}".encode()
            thread = threading.Thread(target=put_data, args=(key, value))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All puts should succeed
        assert all(results)
        # All keys should be retrievable
        for i in range(10):
            key = f"key_{i}"
            value = f"value_{i}".encode()
            assert store.get(key) == value

        store.clear_all()
