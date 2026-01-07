# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Protocol

from marimo._utils.platform import is_pyodide

if not is_pyodide():
    # the shared_memory module is not supported in the Pyodide distribution
    from multiprocessing import shared_memory


class VirtualFileStorage(Protocol):
    """Protocol for virtual file storage backends."""

    def store(self, key: str, buffer: bytes) -> None:
        """Store buffer data by key."""
        ...

    def read(self, key: str, byte_length: int) -> bytes:
        """Read buffer data by key.

        Raises:
            KeyError: If key not found
        """
        ...

    def remove(self, key: str) -> None:
        """Remove stored data by key."""
        ...

    def shutdown(self) -> None:
        """Clean up all storage resources."""
        ...

    def has(self, key: str) -> bool:
        """Check if key exists in storage."""
        ...


class SharedMemoryStorage(VirtualFileStorage):
    """Storage backend using multiprocessing shared memory.

    Used in `edit` mode when kernel runs in a separate process.
    """

    def __init__(self) -> None:
        self._storage: dict[str, shared_memory.SharedMemory] = {}
        self._shutting_down = False

    def store(self, key: str, buffer: bytes) -> None:
        if key in self._storage:
            return  # Already stored

        # Immediately writes the contents of the file to an in-memory
        # buffer; not lazy.
        #
        # To retrieve the buffer from another process, use:
        #
        # ```
        # try:
        #   shm = shared_memory.SharedMemory(name=key)
        #   buffer_contents = bytes(shm.buf)
        # except FileNotFoundError:
        #   # virtual file was removed
        # ```
        shm = shared_memory.SharedMemory(
            name=key,
            create=True,
            size=len(buffer),
        )
        shm.buf[: len(buffer)] = buffer
        # we can safely close this shm, since we don't need to access its
        # buffer; we do need to keep it around so we can unlink it later
        if sys.platform != "win32":
            # don't call close() on Windows, due to a bug in the Windows
            # Python implementation. On Windows, close() actually unlinks
            # (destroys) the shared_memory:
            # https://stackoverflow.com/questions/63713241/segmentation-fault-using-python-shared-memory/63717188#63717188
            shm.close()
        # We have to keep a reference to the shared memory to prevent it from
        # being destroyed on Windows
        self._storage[key] = shm

    def read(self, key: str, byte_length: int) -> bytes:
        if is_pyodide():
            raise RuntimeError(
                "Shared memory is not supported on this platform"
            )
        # Read from shared memory by name (works cross-process)
        shm = None
        try:
            shm = shared_memory.SharedMemory(name=key)
            buffer_contents = bytes(shm.buf)[:byte_length]
        except FileNotFoundError as err:
            raise KeyError(f"Virtual file not found: {key}") from err
        finally:
            if shm is not None:
                shm.close()
        return buffer_contents

    def remove(self, key: str) -> None:
        if key in self._storage:
            if sys.platform == "win32":
                self._storage[key].close()
            self._storage[key].unlink()
            del self._storage[key]

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        try:
            self._shutting_down = True
            for shm in self._storage.values():
                if sys.platform == "win32":
                    shm.close()
                shm.unlink()
            self._storage.clear()
        finally:
            self._shutting_down = False

    def has(self, key: str) -> bool:
        return key in self._storage


class InMemoryStorage(VirtualFileStorage):
    """Storage backend using simple in-memory dictionary.

    Used in `run` mode when kernel runs in the same process as the server.
    """

    def __init__(self) -> None:
        self._storage: dict[str, bytes] = {}

    def store(self, key: str, buffer: bytes) -> None:
        self._storage[key] = buffer

    def read(self, key: str, byte_length: int) -> bytes:
        if key not in self._storage:
            raise KeyError(f"Virtual file not found: {key}")
        return self._storage[key][:byte_length]

    def remove(self, key: str) -> None:
        if key in self._storage:
            del self._storage[key]

    def shutdown(self) -> None:
        self._storage.clear()

    def has(self, key: str) -> bool:
        return key in self._storage


class VirtualFileStorageManager:
    """Singleton manager for virtual file storage access."""

    _instance: VirtualFileStorageManager | None = None
    _storage: VirtualFileStorage | None = None

    def __new__(cls) -> VirtualFileStorageManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def storage(self) -> VirtualFileStorage | None:
        return self._storage

    @storage.setter
    def storage(self, value: VirtualFileStorage | None) -> None:
        self._storage = value

    def read(self, filename: str, byte_length: int) -> bytes:
        """Read from storage, with cross-process fallback for EDIT mode server.

        Raises:
            KeyError: If file not found
            RuntimeError: When ``SharedMemoryStorage`` is used on the Pyodide platform.
        """
        storage = self.storage
        if storage is None:
            # Never initialized so in a separate thread from the kernel.
            # Use SharedMemoryStorage to read by name across processes
            return SharedMemoryStorage().read(filename, byte_length)
        return storage.read(filename, byte_length)
