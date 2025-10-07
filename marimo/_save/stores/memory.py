# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import threading
from multiprocessing import shared_memory
from typing import Optional

from marimo._save.stores.store import Store


class MemoryStore(Store):
    """In-memory cache store using shared memory for cross-process testing.

    This store uses Python's shared_memory module to create memory-backed
    storage that can be accessed across processes without disk I/O.
    Primarily intended for testing the cache system without creating
    persistent artifacts.
    """

    def __init__(self) -> None:
        # Track keys for cleanup
        self._keys: set[str] = set()
        # Lock for thread-safe access
        self._lock = threading.Lock()

    def _shm_name(self, key: str) -> str:
        """Convert cache key to SharedMemory name."""
        # SharedMemory names have restrictions, so prefix and sanitize
        return f"marimo_{key.replace('/', '_').replace('.', '_')}"

    def get(self, key: str) -> Optional[bytes]:
        """Retrieve bytes from shared memory by key."""
        shm_name = self._shm_name(key)
        try:
            # Open existing shared memory block
            shm = shared_memory.SharedMemory(name=shm_name)
            # First 8 bytes store the actual data size
            size = int.from_bytes(shm.buf[:8], 'little')
            # Read the actual data
            data = bytes(shm.buf[8:8+size])
            shm.close()
            return data
        except FileNotFoundError:
            return None

    def put(self, key: str, value: bytes) -> bool:
        """Store bytes in shared memory."""
        # Clean up old shared memory block if key exists
        self.clear(key)

        shm_name = self._shm_name(key)
        try:
            # Create new shared memory block (8 bytes for size header + data)
            data_size = len(value)
            # SharedMemory requires size > 0, so minimum is 8 bytes for header
            total_size = max(8, 8 + data_size)
            shm = shared_memory.SharedMemory(
                name=shm_name,
                create=True,
                size=total_size
            )
            # Write size header (first 8 bytes)
            shm.buf[:8] = data_size.to_bytes(8, 'little')
            # Write the actual data (if any)
            if data_size > 0:
                shm.buf[8:8+data_size] = value
            shm.close()

            # Track key for cleanup
            with self._lock:
                self._keys.add(key)

            return True
        except Exception:
            # Failed to create shared memory
            return False

    def hit(self, key: str) -> bool:
        """Check if key exists in store."""
        shm_name = self._shm_name(key)
        try:
            # Verify shared memory block actually exists
            shm = shared_memory.SharedMemory(name=shm_name)
            shm.close()
            return True
        except FileNotFoundError:
            return False

    def clear(self, key: str) -> bool:
        """Delete shared memory block for key."""
        shm_name = self._shm_name(key)
        try:
            # Unlink the shared memory block
            shm = shared_memory.SharedMemory(name=shm_name)
            shm.close()
            shm.unlink()

            # Remove from tracked keys
            with self._lock:
                self._keys.discard(key)

            return True
        except FileNotFoundError:
            return False

    def clear_all(self) -> None:
        """Clear all stored data and cleanup shared memory."""
        with self._lock:
            keys = list(self._keys)

        for key in keys:
            self.clear(key)

    def __del__(self) -> None:
        """Cleanup all shared memory blocks on deletion."""
        try:
            self.clear_all()
        except Exception:
            # Best effort cleanup
            pass
