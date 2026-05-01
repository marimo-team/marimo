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
from marimo._runtime.virtual_file.virtual_file import (
    read_virtual_file,
    read_virtual_file_chunked,
)
from marimo._utils.http import HTTPException


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

    @pytest.mark.parametrize(
        "key",
        # Keys the OS shared-memory namespace will reject with OSError or
        # ValueError rather than FileNotFoundError. Covers the broadened
        # exception catch in has(): probing must return False, not crash.
        ["", "/", "//", "with/slash", "x" * 4096],
    )
    def test_has_returns_false_on_invalid_keys(self, key: str) -> None:
        storage = SharedMemoryStorage()
        try:
            assert storage.has(key) is False
        finally:
            storage.shutdown()

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

    @pytest.mark.parametrize(
        "key",
        [
            "../escape",
            "../../etc/passwd",
            "foo/bar",
            "foo\\bar",
            "..",
            ".",
            "",
            "with\x00null",
        ],
    )
    def test_rejects_path_traversal_keys(
        self, storage: DiskStorage, key: str
    ) -> None:
        # The /@file/{...:path} HTTP route forwards raw URL segments as
        # keys. DiskStorage must reject path-traversal keys before
        # touching the filesystem so an attacker can't escape base_dir.
        with pytest.raises(KeyError, match="Invalid virtual file key"):
            storage.store(key, b"data")
        with pytest.raises(KeyError, match="Invalid virtual file key"):
            storage.read(key, 10)
        with pytest.raises(KeyError, match="Invalid virtual file key"):
            list(storage.read_chunked(key, 10))
        with pytest.raises(KeyError, match="Invalid virtual file key"):
            storage.remove(key)
        # has() is a query and must return False (not raise) so that
        # FallbackStorage probing doesn't crash on hostile keys.
        assert storage.has(key) is False

    def test_traversal_does_not_create_outside_base_dir(
        self, tmp_path
    ) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        base = tmp_path / "base"
        storage = DiskStorage(base_dir=base)
        with pytest.raises(KeyError):
            storage.store("../outside/leak", b"secret")
        assert not (outside / "leak").exists()


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

    def test_raises_oserror_when_all_backends_stale(self, tmp_path) -> None:
        # If every backend is stale, no store is attempted and last_err
        # stays None — must raise an explicit OSError, not an
        # AssertionError (or TypeError under `python -O`).
        a = DiskStorage(base_dir=tmp_path / "a")
        a.shutdown()
        b = DiskStorage(base_dir=tmp_path / "b")
        b.shutdown()
        fb = FallbackStorage([a, b])
        with pytest.raises(OSError, match="stale"):
            fb.store("k", b"data")

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


class _FailingReadStorage(InMemoryStorage):
    """Stores normally but raises on read — simulates a storage segment that
    was successfully created but becomes unreadable later (corrupted shared
    memory, disk I/O error mid-stream, etc.).
    """

    def __init__(self, exc: BaseException) -> None:
        super().__init__()
        self._exc = exc

    def read(self, key: str, byte_length: int) -> bytes:  # noqa: ARG002
        raise self._exc

    def read_chunked(self, key, byte_length, chunk_size=...):  # type: ignore[override]  # noqa: ARG002
        raise self._exc

    def has(self, key: str) -> bool:  # noqa: ARG002
        return True


class _FailingShutdownStorage(InMemoryStorage):
    """Raises on shutdown. Used to verify that one bad backend doesn't
    block cleanup of the others.
    """

    def shutdown(self, keys=None) -> None:  # noqa: ARG002
        raise OSError(5, "I/O error during shutdown")


class TestKernelResilience:
    """Failure-mode tests: confirm that storage errors don't crash the
    kernel or the HTTP server beyond the affected request/cell.
    """

    def test_read_oserror_returns_404_not_500(self) -> None:
        """An OSError raised during read should surface as a 404
        HTTPException (treated as 'not found' from the client's POV) rather
        than propagating to the server worker as a 500. Otherwise a single
        flaky read crashes the streaming response.
        """
        manager = VirtualFileStorageManager()
        original = manager.storage
        try:
            manager.storage = _FailingReadStorage(
                OSError(5, "I/O error reading shared memory")
            )
            with pytest.raises(HTTPException) as exc:
                read_virtual_file("any-name", 10)
            assert exc.value.status_code == 404
        finally:
            manager.storage = original

    def test_read_chunked_oserror_returns_404_not_500(self) -> None:
        manager = VirtualFileStorageManager()
        original = manager.storage
        try:
            manager.storage = _FailingReadStorage(
                OSError(5, "I/O error reading shared memory")
            )
            with pytest.raises(HTTPException) as exc:
                list(read_virtual_file_chunked("any-name", 10))
            assert exc.value.status_code == 404
        finally:
            manager.storage = original

    def test_fallback_shutdown_tolerates_per_backend_failures(self) -> None:
        """If one backend's shutdown raises, the others must still get
        their shutdown called. Otherwise a transient cleanup error during
        session end leaks shared memory and disk files.
        """
        bad = _FailingShutdownStorage()
        good = InMemoryStorage()
        good.store("k", b"data")
        fb = FallbackStorage([bad, good])
        # Should not raise; the bad backend's failure should be logged and
        # the good backend should still be shut down.
        fb.shutdown()
        assert not good.has("k"), (
            "good backend was not shut down because bad backend raised"
        )

    def test_fallback_shutdown_with_keys_tolerates_failures(self) -> None:
        bad = _FailingShutdownStorage()
        good = InMemoryStorage()
        good.store("k", b"data")
        fb = FallbackStorage([bad, good])
        fb.shutdown(keys=["k"])
        assert not good.has("k")

    def test_read_endpoint_blocks_arbitrary_shared_memory_access(
        self,
    ) -> None:
        """Demonstrates the cross-process SHM read attack: an authenticated
        client requests /@file/<size>-<arbitrary_shm_name>; without
        filename validation, the server's cross-process fallback opens
        that segment by name and serves its contents. With validation,
        non-marimo-shaped filenames are rejected at the boundary.
        """
        from multiprocessing import shared_memory

        # Simulate another process's shared memory segment.
        name = "not_a_marimo_virtual_file_name"
        shm = shared_memory.SharedMemory(name=name, create=True, size=64)
        shm.buf[:6] = b"secret"
        try:
            manager = VirtualFileStorageManager()
            original = manager.storage
            manager.storage = None  # force cross-process probe path
            try:
                with pytest.raises(HTTPException) as exc:
                    read_virtual_file(name, 6)
                assert exc.value.status_code == 404
                with pytest.raises(HTTPException) as exc:
                    list(read_virtual_file_chunked(name, 6))
                assert exc.value.status_code == 404
            finally:
                manager.storage = original
        finally:
            shm.close()
            shm.unlink()

    @pytest.mark.parametrize(
        "filename",
        [
            "/etc/passwd",
            "../../etc/passwd",
            "with space.png",
            "no-extension",
            "..",
            "",
            "12345-abcdefgh.\npng",  # control char
        ],
    )
    def test_read_endpoint_rejects_unmarimo_filenames(
        self, filename: str
    ) -> None:
        with pytest.raises(HTTPException) as exc:
            read_virtual_file(filename, 10)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            list(read_virtual_file_chunked(filename, 10))
        assert exc.value.status_code == 404

    def test_read_endpoint_accepts_marimo_filenames(self) -> None:
        """Sanity: legitimate random_filename outputs pass validation
        (then KeyError-out as 'not found' since nothing is stored).
        Confirms validation isn't over-restrictive.
        """
        manager = VirtualFileStorageManager()
        original = manager.storage
        try:
            manager.storage = InMemoryStorage()
            with pytest.raises(HTTPException) as exc:
                read_virtual_file("12345-AbCdEf12.png", 10)
            assert exc.value.status_code == 404
            assert exc.value.detail == "File not found"
        finally:
            manager.storage = original

    def test_shared_memory_chunked_huge_byte_length_terminates(self) -> None:
        """SharedMemoryStorage.read_chunked must bound iterations by
        the actual segment size, not the URL-supplied byte_length.
        Otherwise an attacker requesting /@file/<huge>-<key> causes the
        loop to yield (huge / chunk_size) chunks — a DoS that can keep
        a worker busy for arbitrarily long.

        Note: shm segments are page-allocated, so a 2-byte store actually
        backs onto ~one page; we just need to confirm the response stays
        bounded near the page size, not anywhere near byte_length.
        """
        storage = SharedMemoryStorage()
        try:
            storage.store("marimo_dos_test", b"hi")
            chunks = list(
                storage.read_chunked(
                    "marimo_dos_test",
                    byte_length=10**10,
                    chunk_size=1024,
                )
            )
            total = sum(len(c) for c in chunks)
            # A 2-byte store should never expand into megabytes of
            # response just because the URL asked for a huge length.
            assert total < 10**6, (
                f"DoS regression: returned {total} bytes for a 2-byte file"
            )
            assert len(chunks) > 0
            assert chunks[0].startswith(b"hi")
        finally:
            storage.shutdown()

    def test_disk_storage_rejects_symlinked_base_dir(self, tmp_path) -> None:
        """DiskStorage must refuse to use a base_dir that exists as
        a symlink — defends against the classic /tmp pre-creation attack
        where a co-tenant pre-creates `/tmp/marimo-vfs` as a symlink to
        an attacker-controlled directory.
        """
        target = tmp_path / "real"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)
        with pytest.raises(OSError, match="symlink"):
            DiskStorage(base_dir=link)

    def test_disk_storage_read_chunked_propagates_mid_stream_error(
        self, tmp_path
    ) -> None:
        """DiskStorage.read_chunked is a generator. If the file is
        removed mid-stream, the open fd survives (POSIX inode semantics)
        and remaining chunks still come from the file's contents — not
        from disk lookup of the (now-missing) name. Captures this
        behaviour so any change is intentional.
        """
        storage = DiskStorage(base_dir=tmp_path)
        storage.store("k", b"x" * 1000)
        gen = storage.read_chunked("k", 1000, chunk_size=100)
        first = next(gen)
        assert len(first) == 100
        # Delete the file out from under the generator.
        (tmp_path / "k").unlink()
        # Remaining chunks should still come from the open file handle
        # (POSIX semantics: the inode lives until the fd is closed).
        rest = b"".join(gen)
        assert len(first) + len(rest) == 1000


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
