# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import tempfile
from pathlib import Path
from unittest import mock

import msgspec
import pytest

from marimo._save.cache import MARIMO_CACHE_VERSION, Cache
from marimo._save.loaders.lazy import (
    _ACTIVE_LAZY_LOADERS,
    LazyLoader,
    LazyStore,
    WasmLazyLoader,
    WasmLazyStore,
)
from marimo._save.stores.dict_store import DictStore
from marimo._save.stores.file import FileStore
from marimo._save.stores.store import Store
from marimo._save.stubs.lazy_stub import (
    Cache as CacheSchema,
    CacheType,
    Item,
    Meta,
)


class TestDictStore:
    def test_get_put_hit(self) -> None:
        store = DictStore()
        assert store.get("k") is None
        assert not store.hit("k")

        assert store.put("k", b"v")
        assert store.get("k") == b"v"
        assert store.hit("k")

    def test_clear(self) -> None:
        store = DictStore()
        store.put("k", b"v")
        assert store.clear("k")
        assert not store.hit("k")
        assert not store.clear("k")  # already gone

    def test_get_batch_default_sequential(self) -> None:
        # DictStore inherits the base Store sequential get_batch.
        store = DictStore()
        store.put("a", b"1")
        assert dict(store.get_batch(["a", "missing"])) == {
            "a": b"1",
            "missing": None,
        }

    def test_export_keys_defaults_empty(self) -> None:
        # Non-tracking stores inherit the inert base Store default.
        store = DictStore()
        store.put("a", b"1")
        assert store.export_keys() == []


class TestLazyStoreNative:
    """Test LazyStore in native (non-Pyodide) mode."""

    def test_is_store(self) -> None:
        store = LazyStore(inner=DictStore())
        assert isinstance(store, Store)

    def test_delegates_to_inner(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inner = FileStore(td)
            store = LazyStore(inner=inner)

            assert store.put("blob.bin", b"data")
            assert store.get("blob.bin") == b"data"
            assert store.hit("blob.bin")

            # Verify it was written to the inner FileStore
            assert (Path(td) / "blob.bin").read_bytes() == b"data"

    def test_get_returns_none_for_missing(self) -> None:
        store = LazyStore(inner=DictStore())
        assert store.get("nonexistent") is None

    def test_get_batch_sequential(self) -> None:
        inner = DictStore()
        store = LazyStore(inner=inner)
        store.put("a.bin", b"aa")
        store.put("b.bin", b"bb")
        store.put("c.bin", b"cc")

        results = dict(store.get_batch(["a.bin", "b.bin", "c.bin"]))
        assert results == {
            "a.bin": b"aa",
            "b.bin": b"bb",
            "c.bin": b"cc",
        }

    def test_get_batch_missing_key(self) -> None:
        store = LazyStore(inner=DictStore())
        store.put("a.bin", b"aa")
        results = dict(store.get_batch(["a.bin", "missing"]))
        assert results["a.bin"] == b"aa"
        assert results["missing"] is None

    def test_export_keys_tracks_puts(self) -> None:
        store = LazyStore(inner=DictStore())
        assert store.export_keys() == []

        store.put("x.bin", b"x")
        store.put("y.bin", b"y")
        assert store.export_keys() == ["x.bin", "y.bin"]

    def test_export_keys_clear_removes(self) -> None:
        store = LazyStore(inner=DictStore())
        store.put("x.bin", b"x")
        store.clear("x.bin")
        assert store.export_keys() == []

    def test_default_inner_is_filestore(self) -> None:
        """Without Pyodide, default inner store is FileStore."""
        store = LazyStore()
        assert isinstance(store._inner, FileStore)


class TestLazyStoreWasm:
    """Test the WASM store variant (`WasmLazyStore`).

    The native/WASM decision is made once via the dual-loader registry
    (`resolve_loader` in `loaders/__init__.py`), so the WASM behaviour lives
    in the `WasmLazyStore` subclass rather than runtime `is_pyodide()`
    branching inside `LazyStore`.
    """

    def test_wasm_default_inner_is_dictstore(self) -> None:
        store = WasmLazyStore()
        assert isinstance(store._inner, DictStore)

    def test_wasm_put_writes_to_dict(self) -> None:
        store = WasmLazyStore(inner=DictStore())
        assert store.put("k", b"v")
        # Read from inner directly (no HTTP)
        assert store._inner.get("k") == b"v"

    def test_wasm_get_inner_first(self) -> None:
        store = WasmLazyStore(inner=DictStore())
        store._inner.put("k", b"cached")
        # Should return from inner without HTTP
        assert store.get("k") == b"cached"

    @mock.patch("urllib.request.urlopen")
    def test_wasm_get_falls_back_to_http(
        self, mock_urlopen: mock.Mock
    ) -> None:
        store = WasmLazyStore(inner=DictStore())

        # Mock HTTP response
        mock_resp = mock.MagicMock()
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b"from_http"
        mock_urlopen.return_value = mock_resp

        # Mock notebook_location for _base_url
        with mock.patch(
            "marimo._save.loaders.lazy.WasmLazyStore._base_url",
            return_value="http://example.com/public/cache",
        ):
            result = store.get("some/blob.bin")

        assert result == b"from_http"
        mock_urlopen.assert_called_once()
        # Successful fetch is cached in-session and recorded for export,
        # so repeat reads stay local and the bundle ships it.
        assert store._inner.get("some/blob.bin") == b"from_http"
        assert "some/blob.bin" in store.export_keys()

    def test_wasm_http_error_returns_none(self) -> None:
        store = WasmLazyStore(inner=DictStore())
        with (
            mock.patch(
                "urllib.request.urlopen",
                side_effect=Exception("network"),
            ),
            mock.patch(
                "marimo._save.loaders.lazy.WasmLazyStore._base_url",
                return_value="http://example.com/public/cache",
            ),
        ):
            assert store.get("missing.bin") is None


class TestKeySanitization:
    def test_valid_key(self) -> None:
        assert (
            WasmLazyStore._sanitize_key("hash1/var.pickle")
            == "hash1/var.pickle"
        )

    def test_rejects_parent_traversal(self) -> None:
        with pytest.raises(ValueError, match="Invalid cache key"):
            WasmLazyStore._sanitize_key("../etc/passwd")

    def test_rejects_absolute_path(self) -> None:
        with pytest.raises(ValueError, match="Invalid cache key"):
            WasmLazyStore._sanitize_key("/etc/passwd")

    def test_rejects_embedded_dotdot(self) -> None:
        with pytest.raises(ValueError, match="Invalid cache key"):
            WasmLazyStore._sanitize_key("foo/../../bar")


class TestLazyLoaderBatchPath:
    """Test that LazyLoader uses get_batch via the store.get_batch path."""

    def test_restore_uses_batch_path(self) -> None:
        inner = DictStore()
        store = LazyStore(inner=inner)
        loader = LazyLoader("test_batch", store=store)

        # Seed a cache manually
        base = Path("test_batch") / "hash1"
        var_ref = (base / "var1.pickle").as_posix()
        store.put(var_ref, pickle.dumps("value1"))

        manifest = msgspec.json.encode(
            CacheSchema(
                hash="hash1",
                cache_type=CacheType("Pure"),
                defs={"var1": Item(reference=var_ref)},
                stateful_refs=[],
                meta=Meta(version=MARIMO_CACHE_VERSION),
            )
        )
        cache_path = loader.build_path(
            type("Key", (), {"hash": "hash1", "cache_type": "Pure"})()
        )
        store.put(str(cache_path), manifest)

        # Load — should use get_batch path (no threads)
        from marimo._save.hash import HashKey

        key = HashKey(hash="hash1", cache_type="Pure")
        loaded = loader.load_cache(key)
        assert loaded is not None
        assert loaded.defs["var1"] == "value1"

    def test_save_cache_sync_in_wasm(self) -> None:
        # `WasmLazyLoader` is the WASM variant: it writes synchronously
        # (no threads in Pyodide) via `_dispatch_write`.
        inner = DictStore()
        store = WasmLazyStore(inner=inner)
        loader = WasmLazyLoader("test_sync", store=store)

        cache = Cache(
            defs={"x": 42, "y": "hello"},
            hash="sync_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)

        # Verify blobs were written to the DictStore
        assert store.export_keys()  # something was written

        # Load back in native mode (so we don't need js module).
        # The data is in the DictStore inner, and get_batch uses
        # the native sequential path.
        from marimo._save.hash import HashKey

        key = HashKey(hash="sync_hash", cache_type="Pure")
        loaded = loader.load_cache(key)
        assert loaded is not None
        assert loaded.defs["x"] == 42
        assert loaded.defs["y"] == "hello"


class TestFlushAll:
    def test_flush_all_flushes_active_loaders(self) -> None:
        inner = DictStore()
        store1 = LazyStore(inner=inner)
        store2 = LazyStore(inner=DictStore())
        loader1 = LazyLoader("flush_a", store=store1)
        loader2 = LazyLoader("flush_b", store=store2)

        assert _ACTIVE_LAZY_LOADERS.get("flush_a") is loader1
        assert _ACTIVE_LAZY_LOADERS.get("flush_b") is loader2

        # flush_all should not raise
        LazyLoader.flush_all()

    def test_loaders_tracked_by_name(self) -> None:
        """Loaders are tracked in the active dict by name."""
        loader = LazyLoader("track_test", store=LazyStore(inner=DictStore()))
        assert _ACTIVE_LAZY_LOADERS["track_test"] is loader

    def test_store_reused_across_recreations(self) -> None:
        """When a loader is recreated with the same name, it reuses the
        previous loader's store (preserving DictStore data)."""
        store1 = LazyStore(inner=DictStore())
        loader1 = LazyLoader("reuse_test", store=store1)
        store1.put("key1", b"data1")

        # Recreate without explicit store — should reuse store1
        loader2 = LazyLoader("reuse_test")
        assert loader2.store is store1
        assert loader2.store.get("key1") == b"data1"
