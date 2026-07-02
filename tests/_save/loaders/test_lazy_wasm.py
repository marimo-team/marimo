# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import msgspec
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._save.hash import HashKey

from marimo._save.cache import MARIMO_CACHE_VERSION, Cache
from marimo._save.loaders.lazy import (
    LazyLoader,
    LazyStore,
    WasmLazyLoader,
    WasmLazyStore,
    _cache_state,
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


class TestRestoreTripwire:
    """A cached def whose codec needs an absent package binds as a use-site
    tripwire instead of aborting the whole restore. The return value is
    excluded so a stubbed return never becomes the cell's output."""

    @pytest.fixture(autouse=True)
    def _isolate_poisoned_keys(self) -> Iterator[None]:
        # A restore failure (e.g. the WASM return-value test) poisons keys on
        # the shared process-local CacheState; snapshot/restore so it doesn't
        # leak into other classes' exact-poison-set assertions.
        poisoned = _cache_state().poisoned_keys
        snapshot = set(poisoned)
        yield
        poisoned.clear()
        poisoned.update(snapshot)

    @staticmethod
    def _patch_failing_codec(monkeypatch: pytest.MonkeyPatch) -> None:
        # A `.faildep` codec that always raises ModuleNotFoundError, standing
        # in for e.g. a torch tensor restored where torch is not installed.
        from marimo._save.loaders import lazy as lazy_mod

        def _boom(_data: bytes, _type_hint: str | None = None) -> object:
            raise ModuleNotFoundError("No module named 'torch'")

        monkeypatch.setitem(lazy_mod.BLOB_DESERIALIZERS, ".faildep", _boom)

    @staticmethod
    def _patch_failing_pickle(monkeypatch: pytest.MonkeyPatch) -> None:
        # Fail `.pickle` deserialization only for a sentinel payload, so a
        # single blob (e.g. shared `ui.pickle`) can be made undeserializable
        # while other pickled blobs still load normally.
        from marimo._save.loaders import lazy as lazy_mod

        real = lazy_mod.BLOB_DESERIALIZERS[".pickle"]

        def _maybe_boom(data: bytes, type_hint: str | None = None) -> object:
            if data == b"__FAIL__":
                raise ModuleNotFoundError("No module named 'torch'")
            return real(data, type_hint)

        monkeypatch.setitem(lazy_mod.BLOB_DESERIALIZERS, ".pickle", _maybe_boom)

    @staticmethod
    def _seed(
        store: Store,
        loader: LazyLoader,
        defs: dict,
        meta: Meta,
        ui_defs: list[str] | None = None,
    ) -> None:
        from marimo._save.hash import HashKey

        manifest = msgspec.json.encode(
            CacheSchema(
                hash="h",
                cache_type=CacheType("Pure"),
                defs=defs,
                stateful_refs=[],
                meta=meta,
                ui_defs=ui_defs or [],
            )
        )
        key = HashKey(hash="h", cache_type="Pure")
        store.put(str(loader.build_path(key)), manifest)

    def _assert_tripwire(self, loader: LazyLoader) -> None:
        from marimo._runtime.exceptions import MarimoUnhashableCacheError
        from marimo._save.hash import HashKey

        loaded = loader.load_cache(HashKey(hash="h", cache_type="Pure"))
        assert loaded is not None
        assert loaded.hit is True
        # The healthy def restored normally.
        assert loaded.defs["good"] == "ok"
        # The missing-dep def is a use-site tripwire naming itself.
        stub = loaded.defs["bad"]
        assert getattr(type(stub), "__marimo_unhashable__", False) is True
        assert stub.var_name == "bad"
        assert stub.type_name == "torch.Tensor"
        # Inert until touched; a real access raises a clear unhydratable error.
        with pytest.raises(MarimoUnhashableCacheError):
            stub()

    def test_def_blob_missing_dep_binds_tripwire_native(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_failing_codec(monkeypatch)
        store = LazyStore(inner=DictStore())
        loader = LazyLoader("trip_native", store=store)

        base = Path("trip_native") / "h"
        good_ref = (base / "good.pickle").as_posix()
        bad_ref = (base / "bad.faildep").as_posix()
        store.put(good_ref, pickle.dumps("ok"))
        store.put(bad_ref, b"unused")
        self._seed(
            store,
            loader,
            {
                "good": Item(reference=good_ref),
                "bad": Item(reference=bad_ref, type_hint="torch.Tensor"),
            },
            Meta(version=MARIMO_CACHE_VERSION),
        )
        self._assert_tripwire(loader)

    def test_def_blob_missing_dep_binds_tripwire_wasm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Exercises the WASM `_read_blobs` variant (get_batch, no threads).
        self._patch_failing_codec(monkeypatch)
        store = WasmLazyStore(inner=DictStore())
        loader = WasmLazyLoader("trip_wasm", store=store)

        base = Path("trip_wasm") / "h"
        good_ref = (base / "good.pickle").as_posix()
        bad_ref = (base / "bad.faildep").as_posix()
        store.put(good_ref, pickle.dumps("ok"))
        store.put(bad_ref, b"unused")
        self._seed(
            store,
            loader,
            {
                "good": Item(reference=good_ref),
                "bad": Item(reference=bad_ref, type_hint="torch.Tensor"),
            },
            Meta(version=MARIMO_CACHE_VERSION),
        )
        self._assert_tripwire(loader)

    def test_return_blob_missing_dep_is_not_stubbed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A return value that can't deserialize must NOT become a stubbed
        # output; the restore fails cleanly (miss) instead.
        self._patch_failing_codec(monkeypatch)
        from marimo._save.hash import HashKey

        store = LazyStore(inner=DictStore())
        loader = LazyLoader("trip_return", store=store)

        base = Path("trip_return") / "h"
        good_ref = (base / "good.pickle").as_posix()
        ret_ref = (base / "return.faildep").as_posix()
        store.put(good_ref, pickle.dumps("ok"))
        store.put(ret_ref, b"unused")
        self._seed(
            store,
            loader,
            {"good": Item(reference=good_ref)},
            Meta(
                version=MARIMO_CACHE_VERSION,
                return_value=Item(reference=ret_ref, type_hint="torch.Tensor"),
            ),
        )
        # Clean miss — no stub leaks out as the cell output.
        assert loader.load_cache(HashKey(hash="h", cache_type="Pure")) is None

    def test_return_blob_missing_dep_is_not_stubbed_wasm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Same exclusion on the WASM restore path (get_batch): the re-raised
        # ModuleNotFoundError bubbles to load_cache, which returns None.
        self._patch_failing_codec(monkeypatch)
        from marimo._save.hash import HashKey

        store = WasmLazyStore(inner=DictStore())
        loader = WasmLazyLoader("trip_return_wasm", store=store)

        base = Path("trip_return_wasm") / "h"
        good_ref = (base / "good.pickle").as_posix()
        ret_ref = (base / "return.faildep").as_posix()
        store.put(good_ref, pickle.dumps("ok"))
        store.put(ret_ref, b"unused")
        self._seed(
            store,
            loader,
            {"good": Item(reference=good_ref)},
            Meta(
                version=MARIMO_CACHE_VERSION,
                return_value=Item(reference=ret_ref, type_hint="torch.Tensor"),
            ),
        )
        assert loader.load_cache(HashKey(hash="h", cache_type="Pure")) is None

    def test_shared_ui_blob_labels_each_def(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # All UI vars share one `ui.pickle` blob. When it can't deserialize,
        # each UI def must become its OWN tripwire naming itself — not one
        # shared stub reporting an arbitrary sibling's name.
        self._patch_failing_pickle(monkeypatch)
        from marimo._runtime.exceptions import MarimoUnhashableCacheError
        from marimo._save.hash import HashKey

        store = LazyStore(inner=DictStore())
        loader = LazyLoader("trip_ui", store=store)

        ui_ref = (Path("trip_ui") / "h" / "ui.pickle").as_posix()
        store.put(ui_ref, b"__FAIL__")
        self._seed(
            store,
            loader,
            {
                "ui_a": Item(reference=ui_ref),
                "ui_b": Item(reference=ui_ref),
            },
            Meta(version=MARIMO_CACHE_VERSION),
            ui_defs=["ui_a", "ui_b"],
        )

        loaded = loader.load_cache(HashKey(hash="h", cache_type="Pure"))
        assert loaded is not None
        assert loaded.hit is True
        stub_a, stub_b = loaded.defs["ui_a"], loaded.defs["ui_b"]
        # Distinct stubs, each naming the def it backs.
        assert stub_a is not stub_b
        assert stub_a.var_name == "ui_a"
        assert stub_b.var_name == "ui_b"
        for stub in (stub_a, stub_b):
            with pytest.raises(MarimoUnhashableCacheError):
                stub()

    def test_import_error_is_not_downgraded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The catch is narrow: only ModuleNotFoundError becomes a tripwire.
        # A plain ImportError is a genuine failure — it must abort the restore
        # (clean miss), not silently bind a stub.
        from marimo._save.hash import HashKey
        from marimo._save.loaders import lazy as lazy_mod

        def _import_error(_data: bytes, _type_hint: str | None = None) -> object:
            raise ImportError("cannot import name 'X'")

        monkeypatch.setitem(
            lazy_mod.BLOB_DESERIALIZERS, ".faildep", _import_error
        )

        store = LazyStore(inner=DictStore())
        loader = LazyLoader("trip_import", store=store)
        bad_ref = (Path("trip_import") / "h" / "bad.faildep").as_posix()
        store.put(bad_ref, b"unused")
        self._seed(
            store,
            loader,
            {"bad": Item(reference=bad_ref)},
            Meta(version=MARIMO_CACHE_VERSION),
        )
        assert loader.load_cache(HashKey(hash="h", cache_type="Pure")) is None


class TestModuleVersionPin:
    """A module def restored where the module is absent must replay its
    pinned version onto the `MissingModule` placeholder, so a version-pinned
    content hash reproduces instead of collapsing to an empty version (which
    would miss against a natively-exported cache)."""

    def test_module_version_round_trips_through_manifest(self) -> None:
        from types import ModuleType

        from marimo._save.loaders.lazy import from_item, to_item
        from marimo._save.stubs.module_stub import MissingModule, ModuleStub

        fake = ModuleType("torch")
        fake.__version__ = "2.9.1"

        # Capture at cache time.
        stub = ModuleStub(fake)
        assert stub.version == "2.9.1"

        # Persist through the manifest.
        item = to_item(Path("base"), stub, var_name="torch", loader="inline")
        assert item.module == "torch"
        assert item.module_version == "2.9.1"

        # Restore the stub with its version intact.
        restored = from_item(item, "torch")
        assert isinstance(restored, ModuleStub)
        assert restored.version == "2.9.1"

        # With the real module absent, load() yields a MissingModule that
        # still reports the pinned version, so `getattr(mod, "__version__")`
        # reproduces the pinned hash rather than an empty string.
        restored.name = "definitely_not_a_real_module_xyz"
        missing = restored.load()
        assert isinstance(missing, MissingModule)
        assert missing.__version__ == "2.9.1"

    def test_missing_module_absent_version_is_empty(self) -> None:
        # No pinned version (e.g. a submodule with no __version__) degrades to
        # an empty string, not an error, mirroring the pre-existing behavior.
        from marimo._save.stubs.module_stub import MissingModule

        missing = MissingModule("torch.nn")
        assert missing.__version__ == ""


class TestStaleKeys:
    """A manifest marked stale misses without being served or re-fetched, so
    the producing cell re-runs live instead of restoring the same value."""

    def test_mark_stale_forces_miss_without_fetch(self) -> None:
        from marimo._save.hash import HashKey
        from marimo._save.loaders.lazy import _cache_state

        store = LazyStore(inner=DictStore())
        loader = LazyLoader("stale_test", store=store)

        base = Path("stale_test") / "h"
        var_ref = (base / "v.pickle").as_posix()
        store.put(var_ref, pickle.dumps("value"))
        manifest = msgspec.json.encode(
            CacheSchema(
                hash="h",
                cache_type=CacheType("Pure"),
                defs={"v": Item(reference=var_ref)},
                stateful_refs=[],
                meta=Meta(version=MARIMO_CACHE_VERSION),
            )
        )
        key = HashKey(hash="h", cache_type="Pure")
        manifest_key = str(loader.build_path(key))
        store.put(manifest_key, manifest)

        # Hits before marking stale.
        assert loader.load_cache(key) is not None

        # Marking stale forces a miss even though the manifest is present.
        stale = _cache_state().stale_keys
        try:
            loader.mark_stale(manifest_key)
            assert loader.load_cache(key) is None
        finally:
            stale.discard(manifest_key)

    def test_save_cache_clears_stale_mark(self) -> None:
        # stale_keys is session-scoped, so a recovered cell must un-stale its
        # own manifest on save or it would re-run live every round forever.
        from marimo._save.hash import HashKey
        from marimo._save.loaders.lazy import _cache_state

        store = LazyStore(inner=DictStore())
        loader = LazyLoader("stale_save", store=store)
        key = HashKey(hash="h", cache_type="Pure")
        manifest_key = str(loader.build_path(key))

        stale = _cache_state().stale_keys
        try:
            loader.mark_stale(manifest_key)
            assert manifest_key in stale
            # Saving a fresh manifest for that key clears the stale mark.
            loader.save_cache(
                Cache(
                    defs={"v": 1},
                    hash="h",
                    cache_type="Pure",
                    stateful_refs=set(),
                    hit=False,
                    meta={"version": MARIMO_CACHE_VERSION},
                )
            )
            assert manifest_key not in stale
        finally:
            stale.discard(manifest_key)
            loader.flush()


class TestFlushAll:
    def test_flush_all_flushes_active_loaders(self) -> None:
        inner = DictStore()
        store1 = LazyStore(inner=inner)
        store2 = LazyStore(inner=DictStore())
        loader1 = LazyLoader("flush_a", store=store1)
        loader2 = LazyLoader("flush_b", store=store2)

        loaders = _cache_state().active_lazy_loaders
        assert loaders.get("flush_a") is loader1
        assert loaders.get("flush_b") is loader2

        # flush_all should not raise
        LazyLoader.flush_all()

    def test_loaders_tracked_by_name(self) -> None:
        """Loaders are tracked in the active dict by name."""
        loader = LazyLoader("track_test", store=LazyStore(inner=DictStore()))
        assert _cache_state().active_lazy_loaders["track_test"] is loader

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


class TestCacheStateResolution:
    def test_resolves_to_root_context(self) -> None:
        """Child contexts (embedded apps) share the root's cache state."""
        from types import SimpleNamespace

        from marimo._save.cache import CacheState

        root_cache = CacheState(store=DictStore())
        root = SimpleNamespace(parent=None, cache=root_cache)
        child = SimpleNamespace(
            parent=root, cache=CacheState(store=DictStore())
        )

        with mock.patch(
            "marimo._save.loaders.lazy.safe_get_context", return_value=child
        ):
            assert _cache_state() is root_cache


class TestOnRestoreFailure:
    """`WasmLazyLoader._on_restore_failure`: on a corrupt restore, evict the
    manifest and its referenced blobs from the store and poison their keys so
    the HTTP fallback never re-fetches the same broken data."""

    @pytest.fixture(autouse=True)
    def _isolate_poisoned_keys(self) -> Iterator[None]:
        # Snapshot/restore so poison doesn't leak across tests.
        poisoned = _cache_state().poisoned_keys
        snapshot = set(poisoned)
        yield
        poisoned.clear()
        poisoned.update(snapshot)

    @staticmethod
    def _manifest(refs: list[str], return_ref: str | None = None) -> bytes:
        meta = Meta(version=MARIMO_CACHE_VERSION)
        if return_ref is not None:
            meta = Meta(
                version=MARIMO_CACHE_VERSION,
                return_value=Item(reference=return_ref),
            )
        return msgspec.json.encode(
            CacheSchema(
                hash="h",
                cache_type=CacheType("Pure"),
                defs={f"v{i}": Item(reference=r) for i, r in enumerate(refs)},
                stateful_refs=[],
                meta=meta,
            )
        )

    def _loader_and_key(
        self,
    ) -> tuple[WasmLazyStore, WasmLazyLoader, HashKey]:
        from marimo._save.hash import HashKey

        store = WasmLazyStore(inner=DictStore())
        loader = WasmLazyLoader("restore_fail", store=store)
        return store, loader, HashKey(hash="h", cache_type="Pure")

    def test_evicts_and_poisons_manifest_and_blobs(self) -> None:
        store, loader, key = self._loader_and_key()
        manifest_path = str(loader.build_path(key))
        blob_a, blob_b = "h/a.pickle", "h/b.pickle"
        for k in (manifest_path, blob_a, blob_b):
            store.put(k, b"x")

        loader._on_restore_failure(key, self._manifest([blob_a, blob_b]))

        for k in (manifest_path, blob_a, blob_b):
            assert not store.hit(k), f"{k} not evicted"
            assert k in _cache_state().poisoned_keys, f"{k} not poisoned"

    def test_poisons_return_value_reference(self) -> None:
        store, loader, key = self._loader_and_key()
        ret_ref = "h/return.pickle"
        store.put(ret_ref, b"x")

        loader._on_restore_failure(key, self._manifest([], return_ref=ret_ref))

        assert not store.hit(ret_ref)
        assert ret_ref in _cache_state().poisoned_keys

    def test_none_manifest_poisons_only_manifest_path(self) -> None:
        store, loader, key = self._loader_and_key()
        manifest_path = str(loader.build_path(key))

        loader._on_restore_failure(key, None)

        assert manifest_path in _cache_state().poisoned_keys
        # No blob keys to discover, so nothing else is poisoned.
        assert _cache_state().poisoned_keys == {manifest_path}

    def test_undecodable_manifest_poisons_only_manifest_path(self) -> None:
        store, loader, key = self._loader_and_key()
        manifest_path = str(loader.build_path(key))

        # Garbage bytes must not raise; manifest path is still poisoned.
        loader._on_restore_failure(key, b"not valid msgpack/json")

        assert manifest_path in _cache_state().poisoned_keys
        assert _cache_state().poisoned_keys == {manifest_path}

    def test_corrupt_restore_via_load_cache_poisons_keys(self) -> None:
        # End-to-end: a manifest referencing a missing blob makes restore
        # raise; load_cache swallows it and invokes _on_restore_failure.
        store, loader, key = self._loader_and_key()
        manifest_path = str(loader.build_path(key))
        missing_ref = "h/missing.pickle"
        store._inner.put(manifest_path, self._manifest([missing_ref]))

        # The missing blob would otherwise be fetched over HTTP; stub it to
        # a miss so the restore fails deterministically without network.
        with mock.patch.object(
            store,
            "_http_get_batch",
            return_value=iter([(missing_ref, None)]),
        ):
            assert loader.load_cache(key) is None

        assert manifest_path in _cache_state().poisoned_keys
        assert missing_ref in _cache_state().poisoned_keys
