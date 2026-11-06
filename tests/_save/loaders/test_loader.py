# Copyright 2026 Marimo. All rights reserved.

import json
import os
import pickle
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import msgspec
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._save.cache import MARIMO_CACHE_VERSION, Cache
from marimo._save.hash import HashKey
from marimo._save.loaders import (
    JsonLoader,
    LazyLoader,
    MemoryLoader,
    PickleLoader,
)
from marimo._save.loaders.lazy import LazyStore
from marimo._save.loaders.loader import (
    BasePersistenceLoader,
    Loader,
    LoaderPartial,
)
from marimo._save.stores.dict_store import DictStore
from marimo._save.stores.file import FileStore
from marimo._save.stubs.lazy_stub import (
    Cache as CacheSchema,
    CacheType,
    Item,
    Meta,
    UnhashableStub,
)
from tests._save.loaders.mocks import MockLoader


def key(a, b):
    return HashKey(a, b)


H = "hashhashhashhashhashha"


@pytest.mark.parametrize("has_parent", [False, True])
def test_lazy_store_exports_keys_the_inner_store_kept(
    has_parent: bool,
) -> None:
    store = LazyStore(DictStore())
    if has_parent:
        store.put(f"train/{H}", b"parent")
    store.put(f"train/{H}/value.pickle", b"value")
    assert store.read(f"train/{H}/value.pickle") == b"value"

    assert store.clear(f"train/{H}") is has_parent

    assert store.export_keys() == [f"train/{H}/value.pickle"]
    assert store.read(f"train/{H}/value.pickle") == b"value"


def test_lazy_store_forgets_a_key_the_inner_store_no_longer_holds(
    tmp_path: Path,
) -> None:
    store = LazyStore(FileStore(str(tmp_path)))
    store.put(f"train/P_{H}.pickle", b"value")
    (tmp_path / "train" / f"P_{H}.pickle").unlink()

    assert store.clear(f"train/P_{H}.pickle") is False

    assert store.export_keys() == []


class _CustomLoader(BasePersistenceLoader):
    """A loader from an entry point, with a suffix of its own."""

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, "custom", **kwargs)

    def restore_cache(self, key: HashKey, blob: bytes) -> Cache:
        raise NotImplementedError

    def to_blob(self, cache: Cache) -> bytes:
        raise NotImplementedError


def test_loader_clear_takes_only_its_own_entries(tmp_path: Path) -> None:
    """A store that points to a project writes entries from several loaders
    beside the project files. Each loader clears the entries with its
    suffix, and only a lazy marker names a directory of blobs."""
    store = FileStore(str(tmp_path / "cache[1]"))
    files = {
        f"src/P_{H}.json": b"{}",
        f"src/P_{H}.pickle": b"value",
        f"src/P_{H}.custom": b"custom",
        f"src/{H}/rows.csv": b"1,2",
        "src/records.json": b"[]",
        "src/records/a.json": b"{}",
    }
    for key, value in files.items():
        store.put(key, value)

    for loader, cleared in (
        (JsonLoader("src", store=store), f"src/P_{H}.json"),
        (PickleLoader("src", store=store), f"src/P_{H}.pickle"),
        (_CustomLoader("src", store=store), f"src/P_{H}.custom"),
    ):
        assert loader.clearable_bytes() == len(files[cleared])
        loader.clear()
        assert loader.clearable_bytes() == 0
        del files[cleared]
        assert store.read(cleared) is None
        for key, value in files.items():
            assert store.read(key) == value


def test_lazy_loader_clear_keeps_blobs_a_new_marker_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A writer can write a marker for the same blobs between the listing
    and the removal of the directory."""
    store = FileStore(str(tmp_path))
    loader = LazyLoader("train", store=store, verification="off")
    cache = Cache(
        defs={"z": [1, 2, 3]},
        hash="sharedhashsharedhashsh",
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={"version": MARIMO_CACHE_VERSION},
    )
    assert loader.save_cache(cache)
    loader.flush()
    block = tmp_path / "train"
    blobs = block / "sharedhashsharedhashsh"
    assert blobs.is_dir()
    clear = store.clear

    def clear_then_publish(key: str) -> bool:
        removed = clear(key)
        if key.endswith(".jsonl"):
            (block / "E_sharedhashsharedhashsh.jsonl").write_bytes(b"new")
        return removed

    monkeypatch.setattr(store, "clear", clear_then_publish)
    loader.clear()

    assert not (block / "P_sharedhashsharedhashsh.jsonl").exists()
    assert (block / "E_sharedhashsharedhashsh.jsonl").exists()
    assert blobs.is_dir()


class TestLoaderPartial:
    def test_init(self) -> None:
        """Test initialization."""
        partial = LoaderPartial(MockLoader, config_value="custom")
        assert partial.loader_type == MockLoader
        assert partial.kwargs == {"config_value": "custom"}

    def test_call(self) -> None:
        """Test calling the partial to create a loader."""
        partial = LoaderPartial(MockLoader, config_value="custom")
        loader = partial("test_name")

        assert isinstance(loader, MockLoader)
        assert loader.name == "test_name"
        assert loader.config_value == "custom"

    def test_call_with_invalid_args(self) -> None:
        """Test calling with invalid arguments."""
        partial = LoaderPartial(MockLoader, invalid_arg="value")

        with pytest.raises(TypeError, match="Could not create"):
            partial("test_name")


class ABCTestLoader(ABC):
    suffix = None
    value = None

    def setup_method(self) -> None:
        """Set up a temporary directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = self.temp_dir.name
        self.store = FileStore(save_path=self.save_path)

    def teardown_method(self) -> None:
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def instance(self) -> Loader:
        if self.value is None:
            self.value = self._instance()
        return self.value

    def test_init(self) -> None:
        """Test initialization."""
        loader = self.instance()
        assert loader.name == "test"
        if self.suffix:
            assert loader.suffix == self.suffix
        if isinstance(loader, BasePersistenceLoader):
            assert self.store.save_path.name == Path(self.temp_dir.name).name
            # Check that the directory was created
            assert os.path.exists(self.store.save_path)

    def test_build_path(self) -> None:
        """Test building the path for a cache file."""
        loader = self.instance()
        path = loader.build_path(key("hash1", "Pure"))
        suffix = f".{self.suffix}" if self.suffix else ""
        assert str(path).endswith(f"P_hash1{suffix}")

        path = loader.build_path(key("hash2", "Deferred"))
        assert str(path).endswith(f"D_hash2{suffix}")

    def test_cache_hit_miss(self) -> None:
        """Test cache hit and miss."""
        loader = self.instance()

        # No file exists yet
        assert not loader.cache_hit(key("hash1", "Pure"))

        # Create a cache file
        cache_path = loader.build_path(key("hash1", "Pure"))
        assert cache_path

        # Create a valid JSON cache
        self.seed_cache()

        # Now it should hit
        assert (
            loader.cache_attempt({"var1"}, key("hash1", "Pure"), set())
            is not None
        )

        # Different hash should miss
        assert not loader.cache_hit(key("hash2", "Pure"))

        # Different cache type should miss
        assert not loader.cache_hit(key("hash1", "Deferred"))

        # Empty file should miss
        empty_key = str(loader.build_path(key("empty", "Pure")))
        self.store.put(empty_key, b"")
        assert not loader.cache_hit(key("empty", "Pure"))

        assert loader.hits == 1

    @abstractmethod
    def _instance(self) -> Loader:
        pass

    @abstractmethod
    def seed_cache(self) -> None:
        pass


class TestMemoryLoader(ABCTestLoader):
    def _instance(self) -> Loader:
        return MemoryLoader("test")

    def seed_cache(self) -> None:
        cache_path = self.instance().build_path(key("hash1", "Pure"))
        self.instance()._cache[cache_path] = Cache(
            defs={"var1": "value1"},
            hash="hash1",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={},
        )


class TestJsonLoader(ABCTestLoader):
    suffix = "json"

    def _instance(self) -> Loader:
        return JsonLoader("test", store=self.store)

    def seed_cache(self):
        cache_path = self.instance().build_path(key("hash1", "Pure"))
        cache_dict = {
            "defs": {"var1": "value1"},
            "key": {
                "hash": "hash1",
                "cache_type": "Pure",
            },
            "stateful_refs": [],
            "hit": True,
            "meta": {},
        }

        self.store.put(str(cache_path), json.dumps(cache_dict).encode("utf-8"))


class TestPickleLoader(ABCTestLoader):
    suffix = "pickle"

    def _instance(self) -> Loader:
        return PickleLoader("test", store=self.store)

    def seed_cache(self) -> None:
        cache_path = self.instance().build_path(key("hash1", "Pure"))
        cache = Cache(
            defs={"var1": "value1"},
            hash="hash1",
            cache_type="Pure",
            stateful_refs=set(),
            hit=True,
            meta={},
        )

        self.store.put(str(cache_path), pickle.dumps(cache))


class TestLazyLoader(ABCTestLoader):
    suffix = "jsonl"

    def _instance(self) -> Loader:
        # These exercise generic loader mechanics (hit/miss, blob handling)
        # with hand-written unsigned manifests; signing behavior is covered in
        # test_lazy_signing.py. verification="off" serves unsigned entries as-is.
        return LazyLoader("test", store=self.store, verification="off")

    def teardown_method(self) -> None:
        if self.value and hasattr(self.value, "flush"):
            self.value.flush()
        super().teardown_method()

    def seed_cache(self) -> None:
        loader = self.instance()
        cache_path = loader.build_path(key("hash1", "Pure"))
        base = Path("test") / "hash1"

        # Write the pickle blob for var1
        var_ref = (base / "var1.pickle").as_posix()
        self.store.put(var_ref, pickle.dumps("value1"))

        # Write the manifest
        manifest = msgspec.json.encode(
            CacheSchema(
                hash="hash1",
                cache_type=CacheType("Pure"),
                defs={"var1": Item(reference=var_ref)},
                stateful_refs=[],
                meta=Meta(version=MARIMO_CACHE_VERSION),
            )
        )
        self.store.put(str(cache_path), manifest)

    def test_round_trip(self) -> None:
        """Test save_cache -> flush -> load_cache round-trip."""
        loader = self.instance()

        cache = Cache(
            defs={"x": 42, "y": "hello", "z": [1, 2, 3]},
            hash="round_trip_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        loaded = loader.load_cache(key("round_trip_hash", "Pure"))
        assert loaded is not None
        assert loaded.hash == "round_trip_hash"
        assert loaded.defs["x"] == 42
        assert loaded.defs["y"] == "hello"
        assert loaded.defs["z"] == [1, 2, 3]

    def test_clear_removes_the_blobs_of_an_entry(self) -> None:
        """Clearing takes the blobs of a value stored in parts, and counts
        their bytes as bytes it can free."""
        loader = self.instance()

        cache = Cache(
            defs={"z": [1, 2, 3]},
            hash="clearhashclearhashclea",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()
        block = Path(self.save_path) / "test"
        blobs = block / "clearhashclearhashclea"
        assert blobs.is_dir()
        entry_bytes = sum(
            path.stat().st_size for path in block.rglob("*") if path.is_file()
        )
        blob_bytes = sum(
            path.stat().st_size for path in blobs.rglob("*") if path.is_file()
        )
        assert blob_bytes > 0

        held = loader.clearable_bytes()
        loader.clear()

        assert list(block.iterdir()) == []
        assert held == entry_bytes
        assert loader.clearable_bytes() == 0

    def test_clear_reaches_through_a_wrapping_store(self) -> None:
        """A loader given a wrapped store clears what the inner store wrote,
        and the wrapper no longer lists the blobs for export."""
        store = LazyStore(FileStore(save_path=self.save_path))
        loader = LazyLoader("test", store=store, verification="off")
        cache = Cache(
            defs={"z": [1, 2, 3]},
            hash="wiredhashwiredhashwire",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()
        block = Path(self.save_path) / "test"
        assert loader.clearable_bytes() > 0
        assert any("wiredhashwiredhashwire/" in k for k in store.export_keys())

        loader.clear()

        assert list(block.iterdir()) == []
        assert loader.clearable_bytes() == 0
        assert store.export_keys() == []

    def test_clear_leaves_the_blobs_of_a_loader_sharing_the_block(
        self,
    ) -> None:
        """Two caches can share a block name. Clearing one takes only the
        blob directories its own entries name."""
        loader = self.instance()
        cache = Cache(
            defs={"z": [1, 2, 3]},
            hash="sharedhashsharedhashsh",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()
        block = Path(self.save_path) / "test"
        blobs = block / "sharedhashsharedhashsh"
        assert blobs.is_dir()
        # The other loader wrote the same value under the same hash inline.
        other = block / "P_sharedhashsharedhashsh.pickle"
        other.write_bytes(b"x")

        PickleLoader("test", store=FileStore(save_path=self.save_path)).clear()

        assert not other.exists()
        assert blobs.is_dir()
        restored = loader.load_cache(cache.key)
        assert restored is not None
        assert restored.defs["z"] == [1, 2, 3]

    def test_import_reference_stays_inline(self) -> None:
        """Re-importable references (`from typing import Optional`, an
        imported function/class) are stored inline in the manifest, not as
        per-variable blobs, and restore to the original object by identity."""
        from collections import OrderedDict
        from typing import Optional

        loader = self.instance()
        cache = Cache(
            defs={"Optional": Optional, "OrderedDict": OrderedDict},
            hash="import_ref_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        cache.update({"Optional": Optional, "OrderedDict": OrderedDict})
        assert loader.save_cache(cache)
        loader.flush()

        # No blob files — only the manifest is written.
        blobs = [
            p
            for p in Path(self.store.save_path).rglob("*")
            if p.is_file() and p.suffix != ".jsonl"
        ]
        assert not blobs, f"expected no blobs, found {blobs}"

        loaded = loader.load_cache(key("import_ref_hash", "Pure"))
        assert loaded is not None
        assert loaded.defs["Optional"] is Optional
        assert loaded.defs["OrderedDict"] is OrderedDict

    def test_unserializable_def_marks_manifest_no_blob(self) -> None:
        """A def that can't be serialized (a lambda) writes no blob; the
        manifest `Item` carries `unserializable_type`, and load reconstructs
        an `UnhashableStub` tripwire in-memory."""
        loader = self.instance()
        cache = Cache(
            # `ok` is a list (pickle-blob path); `f` is a lambda (unpicklable).
            defs={"ok": [1, 2, 3], "f": lambda x: x + 1},
            hash="unserializable_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        # No blob written for the lambda — only the serializable `ok` blob
        # and the manifest exist.
        blob_names = sorted(
            p.name
            for p in Path(self.store.save_path).rglob("*")
            if p.is_file() and p.suffix != ".jsonl"
        )
        assert blob_names == ["ok.pickle"], blob_names

        # Manifest marks the lambda's Item, with no dangling reference.
        cache_path = loader.build_path(key("unserializable_hash", "Pure"))
        manifest = self.store.get(str(cache_path))
        decoded = msgspec.json.decode(manifest, type=CacheSchema)
        f_item = decoded.defs["f"]
        assert f_item.reference is None
        assert f_item.unserializable_type is not None
        assert "function" in f_item.unserializable_type.lower()

        # Load: `ok` restores; `f` becomes an in-memory tripwire.
        loaded = loader.load_cache(key("unserializable_hash", "Pure"))
        assert loaded is not None
        assert loaded.defs["ok"] == [1, 2, 3]
        assert isinstance(loaded.defs["f"], UnhashableStub)
        assert loaded.defs["f"].var_name == "f"

    def test_absent_module_blob_not_fetched(self) -> None:
        """A def blob whose type's root module can't be imported here is
        never fetched: restore stands in an `UnhashableStub` carrying the
        persisted content digest so a downstream consumer still reproduces
        its key without the (unmaterializable) value."""
        loader = self.instance()
        base = Path("test") / "absent_hash"
        # Reference a blob intentionally NOT written to the store — if the
        # gate fetched it, restore would miss on the absent blob.
        ref = (base / "t.pt").as_posix()
        manifest = msgspec.json.encode(
            CacheSchema(
                hash="absent_hash",
                cache_type=CacheType("Pure"),
                defs={
                    "t": Item(
                        reference=ref,
                        type_hint="faketorch.Tensor",
                        hash="deadbeef",
                    )
                },
                stateful_refs=[],
                meta=Meta(version=MARIMO_CACHE_VERSION),
            )
        )
        cache_path = loader.build_path(key("absent_hash", "Pure"))
        self.store.put(str(cache_path), manifest)

        requested: list[str] = []
        original_get = self.store.get

        def spy(k: str):
            requested.append(k)
            return original_get(k)

        self.store.get = spy  # type: ignore[method-assign]

        loaded = loader.load_cache(key("absent_hash", "Pure"))
        assert loaded is not None
        stub = loaded.defs["t"]
        assert isinstance(stub, UnhashableStub)
        assert stub.var_name == "t"
        assert stub.type_name == "faketorch.Tensor"
        assert stub.content_hash == "deadbeef"
        # The blob was skipped — only the manifest was fetched.
        assert ref not in requested

    def test_unserializable_ui_clears_ui_defs_and_stale_blob(self) -> None:
        """A UI def that can't be pickled must not leave `ui_defs` pointing
        at `ui.pickle`: restore loads UI defs via `ui_defs`, bypassing the
        per-Item marks, so a stale `ui.pickle` from a prior run would load as
        a phantom hit. On failure `ui_defs` is cleared, each UI Item is
        marked, and the stale blob is removed."""
        from marimo._save.stubs.ui_element_stub import UIElementStub

        loader = self.instance()
        # A UIElementStub instance routes to the "ui" loader by type; give it
        # an unpicklable attribute so the shared ui.pickle write fails.
        ui_stub = UIElementStub.__new__(UIElementStub)
        ui_stub.data = {"bad": lambda: 1}  # type: ignore[attr-defined]

        # Pre-seed a stale ui.pickle at the hash path from a "prior run".
        base = Path("test") / "ui_fail_hash"
        ui_key = (base / "ui.pickle").as_posix()
        self.store.put(ui_key, pickle.dumps({"u": "stale"}))

        cache = Cache(
            defs={"ok": [1, 2, 3], "u": ui_stub},
            hash="ui_fail_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        # Stale ui.pickle removed; the serializable `ok` blob remains.
        assert self.store.get(ui_key) is None
        cache_path = loader.build_path(key("ui_fail_hash", "Pure"))
        decoded = msgspec.json.decode(
            self.store.get(str(cache_path)), type=CacheSchema
        )
        assert decoded.ui_defs == []
        assert decoded.defs["u"].reference is None
        assert decoded.defs["u"].unserializable_type is not None

        # Load: `u` is an in-memory tripwire, not the stale value.
        loaded = loader.load_cache(key("ui_fail_hash", "Pure"))
        assert loaded is not None
        assert loaded.defs["ok"] == [1, 2, 3]
        assert isinstance(loaded.defs["u"], UnhashableStub)

    def test_corrupt_cache_returns_none(self) -> None:
        """Corrupt manifest triggers cache miss, not crash."""
        loader = self.instance()
        cache_path = loader.build_path(key("bad", "Pure"))
        self.store.put(str(cache_path), b"not valid json")

        result = loader.load_cache(key("bad", "Pure"))
        assert result is None

    def test_missing_blob_returns_none(self) -> None:
        """Missing pickle blob triggers cache miss."""
        loader = self.instance()
        cache_path = loader.build_path(key("missing", "Pure"))
        base = Path("test") / "missing"

        # Manifest references a blob that doesn't exist
        manifest = msgspec.json.encode(
            CacheSchema(
                hash="missing",
                cache_type=CacheType("Pure"),
                defs={
                    "var1": Item(reference=(base / "var1.pickle").as_posix())
                },
                stateful_refs=[],
                meta=Meta(version=MARIMO_CACHE_VERSION),
            )
        )
        self.store.put(str(cache_path), manifest)

        result = loader.load_cache(key("missing", "Pure"))
        assert result is None

    @pytest.mark.skipif(
        not DependencyManager.numpy.has(), reason="numpy required"
    )
    def test_numpy_object_dtype_round_trip(self) -> None:
        """Object-dtype numpy arrays survive save → flush → load via .npy."""
        import numpy as np

        loader = self.instance()
        arr = np.array(["a", "b"], dtype=object)
        cache = Cache(
            defs={"arr": arr},
            hash="np_obj_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        loaded = loader.load_cache(key("np_obj_hash", "Pure"))
        assert loaded is not None
        np.testing.assert_array_equal(loaded.defs["arr"], arr)

    @pytest.mark.skipif(
        not DependencyManager.numpy.has(), reason="numpy required"
    )
    def test_numpy_round_trip(self) -> None:
        """numpy arrays survive save → flush → load via .npy format."""
        import numpy as np

        loader = self.instance()
        arr = np.array([1.0, 2.0, 3.0])
        cache = Cache(
            defs={"arr": arr},
            hash="np_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        assert list(Path(self.store.save_path).rglob("*.npy")), (
            "expected .npy blob, got pickle fallback"
        )
        loaded = loader.load_cache(key("np_hash", "Pure"))
        assert loaded is not None
        np.testing.assert_array_equal(loaded.defs["arr"], arr)

    @pytest.mark.skipif(
        not DependencyManager.has("torch"), reason="torch required"
    )
    def test_torch_round_trip(self) -> None:
        """torch tensors survive save → flush → load via the .pt format —
        the manifest reference must match the blob extension."""
        import torch

        loader = self.instance()
        tensor = torch.tensor([1.0, 2.0, 3.0])
        cache = Cache(
            defs={"t": tensor},
            hash="pt_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        assert list(Path(self.store.save_path).rglob("*.pt")), (
            "expected .pt blob, got pickle fallback"
        )
        loaded = loader.load_cache(key("pt_hash", "Pure"))
        assert loaded is not None
        assert torch.equal(loaded.defs["t"], tensor)

    @pytest.mark.skipif(
        not DependencyManager.has("polars"), reason="polars required"
    )
    @pytest.mark.parametrize("pyarrow_available", [True, False])
    def test_polars_round_trip(
        self, monkeypatch: pytest.MonkeyPatch, pyarrow_available: bool
    ) -> None:
        """polars DataFrames survive save → flush → load via .arrow format."""
        import polars as pl

        if not pyarrow_available:
            monkeypatch.setattr(
                DependencyManager.pyarrow, "has", lambda: False
            )
        loader = self.instance()
        df = pl.DataFrame({"a": [1, 2], "b": [3.0, 4.0], "c": ["x", "y"]})
        cache = Cache(
            defs={"df": df},
            hash="pl_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        assert list(Path(self.store.save_path).rglob("*.arrow")), (
            "expected .arrow blob, got pickle fallback"
        )
        loaded = loader.load_cache(key("pl_hash", "Pure"))
        assert loaded is not None
        assert loaded.defs["df"].equals(df)

    @pytest.mark.skipif(
        not DependencyManager.has("polars"), reason="polars required"
    )
    @pytest.mark.parametrize("pyarrow_available", [True, False])
    def test_polars_series_round_trip(
        self, monkeypatch: pytest.MonkeyPatch, pyarrow_available: bool
    ) -> None:
        """polars Series survive save → flush → load via .arrow format."""
        import polars as pl

        if not pyarrow_available:
            monkeypatch.setattr(
                DependencyManager.pyarrow, "has", lambda: False
            )
        loader = self.instance()
        s = pl.Series("vals", ["a", "b", "c"])
        cache = Cache(
            defs={"s": s},
            hash="pl_series_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION},
        )
        assert loader.save_cache(cache)
        loader.flush()

        assert list(Path(self.store.save_path).rglob("*.arrow")), (
            "expected .arrow blob, got pickle fallback"
        )
        loaded = loader.load_cache(key("pl_series_hash", "Pure"))
        assert loaded is not None
        assert isinstance(loaded.defs["s"], pl.Series)
        assert loaded.defs["s"].to_list() == s.to_list()

    @pytest.mark.skipif(
        not DependencyManager.has("polars"), reason="polars required"
    )
    @pytest.mark.parametrize("stored_version", [None, 5, 6])
    def test_polars_cache_versions_reuse_values(
        self, stored_version: int | None
    ) -> None:
        import polars as pl

        loader = self.instance()
        frame = pl.DataFrame({"value": [1, 2]})
        cache = Cache(
            defs={"frame": frame},
            hash="versioned_polars",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={} if stored_version is None else {"version": stored_version},
        )
        assert loader.save_cache(cache)
        loader.flush()
        restored = loader.cache_attempt({"frame"}, cache.key, set())
        assert restored.hit
        assert restored.defs["frame"].equals(frame)
        assert restored.meta["version"] == (
            MARIMO_CACHE_VERSION if stored_version is None else stored_version
        )

    @pytest.mark.skipif(
        not DependencyManager.has("pandas"), reason="pandas required"
    )
    @pytest.mark.parametrize("pyarrow_available", [True, False])
    def test_pandas_round_trip(
        self, monkeypatch: pytest.MonkeyPatch, pyarrow_available: bool
    ) -> None:
        """Persist pandas DataFrames with the available serialization backend."""
        import pandas as pd

        if pyarrow_available:
            pytest.importorskip("pyarrow")
        else:
            monkeypatch.setattr(
                DependencyManager.pyarrow, "has", lambda: False
            )
        loader = self.instance()
        df = pd.DataFrame({"to_frame": [1, 2], "write_ipc": [3.0, 4.0]})
        cache = Cache(
            defs={"df": df},
            hash="pd_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION, "return": df},
        )
        assert loader.save_cache(cache)
        loader.flush()

        extension = "arrow" if pyarrow_available else "pickle"
        assert list(Path(self.store.save_path).rglob(f"*.{extension}"))
        loaded = loader.load_cache(key("pd_hash", "Pure"))
        assert loaded is not None
        pd.testing.assert_frame_equal(loaded.defs["df"], df)
        pd.testing.assert_frame_equal(loaded.meta["return"], df)

    @pytest.mark.skipif(
        not DependencyManager.has("pandas"), reason="pandas required"
    )
    @pytest.mark.parametrize("pyarrow_available", [True, False])
    def test_pandas_series_round_trip(
        self, monkeypatch: pytest.MonkeyPatch, pyarrow_available: bool
    ) -> None:
        """Persist pandas Series with the available serialization backend."""
        import pandas as pd

        if pyarrow_available:
            pytest.importorskip("pyarrow")
        else:
            monkeypatch.setattr(
                DependencyManager.pyarrow, "has", lambda: False
            )
        loader = self.instance()
        s = pd.Series([10, 20, 30], name="vals")
        cache = Cache(
            defs={"s": s},
            hash="pd_series_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION, "return": s},
        )
        assert loader.save_cache(cache)
        loader.flush()

        extension = "arrow" if pyarrow_available else "pickle"
        assert list(Path(self.store.save_path).rglob(f"*.{extension}"))
        loaded = loader.load_cache(key("pd_series_hash", "Pure"))
        assert loaded is not None
        assert isinstance(loaded.defs["s"], pd.Series)
        pd.testing.assert_series_equal(loaded.defs["s"], s)
        pd.testing.assert_series_equal(loaded.meta["return"], s)

    @pytest.mark.skipif(
        not DependencyManager.has("pandas"), reason="pandas required"
    )
    def test_pandas_mixed_dtype_falls_back_to_pickle(self) -> None:
        """An object column that mixes ints and strings fails in Arrow, so
        the frame is pickled and a cache hit restores it intact."""
        import pandas as pd

        pytest.importorskip("pyarrow")
        loader = self.instance()
        df = pd.DataFrame({"mixed": [1, "two"]})
        cache = Cache(
            defs={"df": df},
            hash="pd_mixed_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION, "return": df},
        )
        assert loader.save_cache(cache)
        loader.flush()

        blob_names = sorted(
            p.name
            for p in Path(self.store.save_path).rglob("*")
            if p.is_file() and p.suffix != ".jsonl"
        )
        assert blob_names == ["df.pickle", "return.pickle"], blob_names

        cache_path = loader.build_path(key("pd_mixed_hash", "Pure"))
        decoded = msgspec.json.decode(
            self.store.get(str(cache_path)), type=CacheSchema
        )
        assert decoded.defs["df"].unserializable_type is None
        assert decoded.meta.return_value.unserializable_type is None

        loaded = loader.load_cache(key("pd_mixed_hash", "Pure"))
        assert loaded is not None
        pd.testing.assert_frame_equal(loaded.defs["df"], df)
        pd.testing.assert_frame_equal(loaded.meta["return"], df)

    def test_typed_serializer_failure_falls_back_to_pickle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the typed serializer chosen for a value raises, the value is
        pickled under a `.pickle` key and restores intact."""
        import marimo._save.loaders.lazy as lazy_module
        from marimo._save.stubs.lazy_stub import BLOB_SERIALIZERS

        def _reject(obj: object) -> bytes:
            raise TypeError(f"cannot encode {type(obj).__name__}")

        monkeypatch.setitem(BLOB_SERIALIZERS, "npy", _reject)
        monkeypatch.setattr(
            lazy_module,
            "maybe_update_lazy_stub",
            lambda value: "npy" if isinstance(value, list) else "pickle",
        )
        loader = self.instance()
        value = [1, "two"]
        cache = Cache(
            defs={"v": value},
            hash="typed_fallback_hash",
            cache_type="Pure",
            stateful_refs=set(),
            hit=False,
            meta={"version": MARIMO_CACHE_VERSION, "return": value},
        )
        assert loader.save_cache(cache)
        loader.flush()

        blob_names = sorted(
            p.name
            for p in Path(self.store.save_path).rglob("*")
            if p.is_file() and p.suffix != ".jsonl"
        )
        assert blob_names == ["return.pickle", "v.pickle"], blob_names

        loaded = loader.load_cache(key("typed_fallback_hash", "Pure"))
        assert loaded is not None
        assert loaded.defs["v"] == value
        assert loaded.meta["return"] == value


@dataclass
class _Opaque:
    """Pickled as a blob rather than written inline."""

    value: int


def test_lazy_write_claims_its_blobs_before_the_first_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A write that dies after the claim leaves a partial marker and no
    entry, so a prune that runs meanwhile leaves the blobs alone."""
    from marimo._save.cache import MARIMO_CACHE_VERSION, Cache
    from marimo._save.cache_dirs import is_partial_write
    from marimo._save.loaders.lazy import LazyLoader
    from marimo._save.stores.file import FileStore

    store = FileStore(save_path=str(tmp_path))
    put = FileStore.put
    claim_came_first: list[bool] = []

    def die_at_first_blob(self: FileStore, key: str, value: bytes) -> bool:
        if not is_partial_write(key.rsplit("/", 1)[-1]):
            block = tmp_path / "train"
            claim_came_first.append(
                any(is_partial_write(p.name) for p in block.iterdir())
            )
            raise OSError("disk full")
        return put(self, key, value)

    monkeypatch.setattr(FileStore, "put", die_at_first_blob)
    loader = LazyLoader("train", store=store)
    cache = Cache(
        defs={"model": _Opaque(1)},
        hash="ab12ab12ab12ab12ab12ab",
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={"version": MARIMO_CACHE_VERSION},
    )

    assert loader.save_cache(cache)
    loader.flush()

    # The blob write and then the marker write both found the claim there.
    assert claim_came_first == [True, True]
    names = [p.name for p in (tmp_path / "train").iterdir()]
    assert len(names) == 1
    assert is_partial_write(names[0])
    assert names[0].startswith("P_ab12ab12ab12ab12ab12ab.jsonl")


@pytest.mark.parametrize("broken_tier", [False, True])
def test_lazy_write_releases_its_claim_through_every_tier(
    tmp_path: Path, broken_tier: bool
) -> None:
    """A tiered store writes through each file store, and a completed write
    leaves no claim in any of them. A tier that cannot be written does not
    stop the write to the others."""
    from marimo._save.cache import MARIMO_CACHE_VERSION, Cache
    from marimo._save.cache_dirs import is_partial_write
    from marimo._save.loaders.lazy import LazyLoader
    from marimo._save.stores.file import FileStore
    from marimo._save.stores.tiered import TieredStore

    tiers = [tmp_path / "fast", tmp_path / "slow"]
    stores = [FileStore(save_path=str(tier)) for tier in tiers]
    if broken_tier:
        # A file where the directory belongs makes every write fail.
        (tmp_path / "blocked").write_bytes(b"")
        stores.insert(0, FileStore(save_path=str(tmp_path / "blocked")))
    store = TieredStore(stores)
    loader = LazyLoader("train", store=store)
    cache = Cache(
        defs={"model": _Opaque(1)},
        hash="ab12ab12ab12ab12ab12ab",
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={"version": MARIMO_CACHE_VERSION},
    )

    assert loader.save_cache(cache)
    loader.flush()

    for tier in tiers:
        names = {p.name for p in (tier / "train").iterdir()}
        assert "P_ab12ab12ab12ab12ab12ab.jsonl" in names
        assert not any(is_partial_write(name) for name in names)
