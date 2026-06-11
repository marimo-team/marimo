# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import queue
import threading
from collections.abc import Iterable, Iterator
from enum import Enum, auto
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import msgspec

if TYPE_CHECKING:
    from collections.abc import Callable

from marimo import _loggers
from marimo._save.cache import (
    MARIMO_CACHE_VERSION,
    Cache,
)
from marimo._save.hash import HashKey
from marimo._save.loaders.loader import BasePersistenceLoader
from marimo._save.loaders.unpickler import pickle_load_with_namespace
from marimo._save.stores import FileStore, Store
from marimo._save.stores.store import WasmExportableStore
from marimo._save.stubs import (
    ClassStub,
    FunctionStub,
    ModuleStub,
)
from marimo._save.stubs.lazy_stub import (
    _LAZY_STUB_CACHE,
    BLOB_DESERIALIZERS,
    BLOB_SERIALIZERS,
    LAZY_STUB_LOOKUP,
    Cache as CacheSchema,
    CacheType,
    ImmediateReferenceStub,
    Item,
    Meta,
    ReferenceStub,
    UnhashableStub,
)
from marimo._save.stubs.stubs import mro_lookup
from marimo._utils.platform import is_pyodide

LOGGER = _loggers.marimo_logger()


class _BlobStatus(Enum):
    """Sentinel placed in the results queue when a blob is missing."""

    MISSING = auto()


def maybe_update_lazy_stub(value: Any) -> str:
    """Return the loader strategy string for *value*, caching the result.

    Walks the MRO of `type(value)` against `LAZY_STUB_LOOKUP` (a
    fq-class-name → loader-string registry).  Falls back to `"pickle"`
    when no match is found.
    """
    value_type = type(value)
    if value_type in _LAZY_STUB_CACHE:
        return _LAZY_STUB_CACHE[value_type]
    result = mro_lookup(value_type, LAZY_STUB_LOOKUP)
    loader = result[1] if result else "pickle"
    _LAZY_STUB_CACHE[value_type] = loader
    return loader


def to_item(
    path: Path,
    value: Any | None,
    var_name: str = "",
    loader: str | None = None,
    hash: str | None = "",  # noqa: A002
) -> Item:
    if value is None:
        return Item()

    if loader is None:
        loader = maybe_update_lazy_stub(value)

    type_hint = f"{type(value).__module__}.{type(value).__name__}"

    if loader == "pickle":
        return Item(
            reference=(path / f"{var_name}.pickle").as_posix(),
            hash=hash,
            type_hint=type_hint,
        )
    if loader == "npy":
        return Item(
            reference=(path / f"{var_name}.npy").as_posix(),
            hash=hash,
            type_hint=type_hint,
        )
    if loader == "arrow":
        return Item(
            reference=(path / f"{var_name}.arrow").as_posix(),
            hash=hash,
            type_hint=type_hint,
        )
    if loader == "ui":
        return Item(reference=(path / "ui.pickle").as_posix())
    if isinstance(value, FunctionStub):
        return Item(function=value.dump())
    if isinstance(value, ClassStub):
        return Item(class_def=value.dump())
    if isinstance(value, ModuleStub):
        return Item(module=value.name)
    if isinstance(value, (int, str, float, bool, type(None))):
        return Item(primitive=value)

    return Item(
        reference=(path / f"{var_name}.pickle").as_posix(),
        hash=hash,
        type_hint=type_hint,
    )


def from_item(item: Item) -> Any:
    if item.reference is not None:
        return ImmediateReferenceStub(
            ReferenceStub(item.reference, hash_value=item.hash or "")
        )
    if item.module is not None:
        mod_stub = ModuleStub.__new__(ModuleStub)
        mod_stub.name = item.module
        return mod_stub
    if item.function is not None:
        fn_stub = FunctionStub.__new__(FunctionStub)
        fn_stub.code, fn_stub.filename, fn_stub.lineno = item.function
        return fn_stub
    if item.class_def is not None:
        return ClassStub.from_dump(item.class_def)
    if item.primitive is not None:
        return item.primitive
    return None


# Module-level singleton DictStore for WASM. Shared across all LazyStore
# instances so cached data survives loader recreation (State GC, partial
# reconstruction, etc.).
_WASM_DICT_STORE: Store | None = None


def _get_wasm_dict_store() -> Store:
    global _WASM_DICT_STORE
    if _WASM_DICT_STORE is None:
        from marimo._save.stores.dict_store import DictStore

        _WASM_DICT_STORE = DictStore()
    return _WASM_DICT_STORE


# Module-level poisoned keys — survives across LazyStore instances.
_POISONED_KEYS: set[str] = set()


class LazyStore(WasmExportableStore):
    """Dual-mode store for LazyLoader.

    Native: delegates to inner store (default FileStore at __marimo__/cache/).
    WASM: writes go to a shared DictStore singleton; reads try inner first,
          then HTTP fetch from notebook_location()/public/cache/.
    """

    def __init__(self, inner: Store | None = None) -> None:
        if inner is None:
            if is_pyodide():
                inner = _get_wasm_dict_store()
            else:
                inner = FileStore()
        self._inner = inner
        self._written_keys: set[str] = set()
        print(f"[lazy] LazyStore.__init__: inner={type(inner).__name__}, id={id(inner)}")

    def get(self, key: str) -> bytes | None:
        result = self._inner.get(key)
        if result is not None:
            return result
        if is_pyodide() and key not in _POISONED_KEYS:
            return self._http_get(key)
        return None

    def put(self, key: str, value: bytes) -> bool:
        self._written_keys.add(key)
        return self._inner.put(key, value)

    def hit(self, key: str) -> bool:
        return self._inner.hit(key)

    def clear(self, key: str) -> bool:
        self._written_keys.discard(key)
        return self._inner.clear(key)

    def get_batch(
        self, keys: Iterable[str]
    ) -> Iterator[tuple[str, bytes | None]]:
        if is_pyodide():
            # Check inner store first; only HTTP-fetch keys that miss
            # and aren't poisoned (failed deserialization previously).
            http_keys: list[str] = []
            inner_results: list[tuple[str, bytes]] = []
            for k in keys:
                data = self._inner.get(k)
                if data is not None:
                    inner_results.append((k, data))
                elif k not in _POISONED_KEYS:
                    http_keys.append(k)
                else:
                    inner_results.append((k, None))  # type: ignore[arg-type]
            yield from inner_results
            if http_keys:
                yield from self._http_get_batch(http_keys)
        else:
            for k in keys:
                yield k, self.get(k)

    def export_manifest(self) -> list[str]:
        return sorted(self._written_keys)

    # -- WASM internals --

    def _base_url(self) -> str:
        from marimo._runtime.runtime import notebook_location

        loc = notebook_location()
        return f"{loc}/public/cache" if loc else "public/cache"

    @staticmethod
    def _sanitize_key(key: str) -> str:
        """Prevent path traversal in HTTP fetch keys."""
        clean = PurePosixPath(key)
        if ".." in clean.parts or clean.is_absolute():
            raise ValueError(f"Invalid cache key: {key}")
        return str(clean)

    def _http_get(self, key: str) -> bytes | None:
        """Single sync fetch via pyodide_http-patched urllib."""
        import urllib.request

        key = self._sanitize_key(key)
        url = f"{self._base_url()}/{key}"
        try:
            with urllib.request.urlopen(url) as resp:
                return resp.read() if resp.status == 200 else None
        except Exception:
            return None

    def _http_get_batch(
        self, keys: Iterable[str]
    ) -> Iterator[tuple[str, bytes | None]]:
        """Fire all fetches concurrently via JS fetch + asyncio.gather."""
        import asyncio

        from js import fetch  # type: ignore[import-not-found]

        base = self._base_url()
        keys_list = [self._sanitize_key(k) for k in keys]
        loop = asyncio.get_event_loop()

        async def _fetch_one(key: str) -> tuple[str, bytes | None]:
            resp = await fetch(f"{base}/{key}")
            if resp.ok:
                buf = await resp.arrayBuffer()
                return key, buf.to_bytes()
            return key, None

        async def _fetch_all() -> list[tuple[str, bytes | None]]:
            return await asyncio.gather(
                *(_fetch_one(k) for k in keys_list)
            )

        results = loop.run_until_complete(_fetch_all())
        yield from results


_ACTIVE_LAZY_LOADERS: dict[str, LazyLoader] = {}


class LazyLoader(BasePersistenceLoader):
    def __init__(
        self,
        name: str,
        store: Store | None = None,
    ) -> None:
        if store is None:
            prev = _ACTIVE_LAZY_LOADERS.get(name)
            if prev is not None:
                store = prev.store
            else:
                store = LazyStore()
        super().__init__(name, "jsonl", store)
        self._pending: list[threading.Thread] = []
        _ACTIVE_LAZY_LOADERS[name] = self

    def flush(self) -> None:
        """Wait for all pending background writes to complete."""
        for t in self._pending:
            t.join()
        self._pending.clear()

    @classmethod
    def flush_all(cls) -> None:
        """Flush all active LazyLoader instances."""
        for loader in list(_ACTIVE_LAZY_LOADERS.values()):
            loader.flush()

    def load_cache(
        self,
        key: HashKey,
        glbls: dict[str, Any] | None = None,
    ) -> Cache | None:
        try:
            path = str(self.build_path(key))
            print(f"[lazy] load_cache: looking up manifest at {path}")
            blob: bytes | None = self.store.get(path)
            if not blob:
                print("[lazy] load_cache: manifest not found (cache miss)")
                return None
            print(
                f"[lazy] load_cache: manifest found "
                f"({len(blob)} bytes), restoring..."
            )
            result = self.restore_cache(key, blob, glbls=glbls)
            print(
                f"[lazy] load_cache: restore returned {result is not None}"
            )
            return result
        except Exception as e:
            import traceback

            print(f"[lazy] load_cache: EXCEPTION during restore: {e}")
            traceback.print_exc()
            LOGGER.warning("Failed to restore lazy cache: %s", e)
            # Evict bad data and poison the keys so HTTP doesn't
            # re-fetch the same broken blobs.
            self._evict_cache(key, manifest_blob=blob)  # type: ignore[possibly-undefined]
            return None

    def _evict_cache(
        self, key: HashKey, manifest_blob: bytes | None = None
    ) -> None:
        """Remove a failed cache entry and poison its keys.

        When a remote cache loads successfully (HTTP 200) but fails
        during deserialization (e.g. version mismatch), we need to:
        1. Clear the bad data from the inner store
        2. Poison the keys so HTTP doesn't re-fetch the same broken data
        """
        if not isinstance(self.store, LazyStore):
            return
        inner = self.store._inner
        manifest_path = str(self.build_path(key))

        # Parse the manifest blob we already fetched (not from inner
        # store — HTTP results aren't written to DictStore by get()).
        blob_keys: list[str] = []
        if manifest_blob:
            try:
                cache_data = msgspec.json.decode(
                    manifest_blob, type=CacheSchema
                )
                for item in cache_data.defs.values():
                    if item.reference:
                        blob_keys.append(item.reference)
                if (
                    cache_data.meta.return_value
                    and cache_data.meta.return_value.reference
                ):
                    blob_keys.append(
                        cache_data.meta.return_value.reference
                    )
            except Exception:
                pass

        # Clear from inner store + poison so HTTP won't re-fetch
        inner.clear(manifest_path)
        _POISONED_KEYS.add(manifest_path)
        for blob_key in blob_keys:
            inner.clear(blob_key)
            _POISONED_KEYS.add(blob_key)
        print(
            f"[lazy] _evict_cache: evicted + poisoned {manifest_path} "
            f"+ {len(blob_keys)} blobs"
        )

    def restore_cache(
        self,
        _key: HashKey,
        blob: bytes,
        glbls: dict[str, Any] | None = None,
    ) -> Cache:
        cache_data = msgspec.json.decode(blob, type=CacheSchema)
        base = Path(self.name) / cache_data.hash
        print(f"[lazy] restore_cache: hash={cache_data.hash}, defs={list(cache_data.defs.keys())}")

        # PASS 1: materialize inline source-based stubs (ClassStub,
        # FunctionStub) into `glbls` synchronously, so any pickle blob
        # loaded below can resolve __main__ refs to the just-materialized
        # objects via CellNamespaceUnpickler.
        if glbls is not None:
            for var_name, item in cache_data.defs.items():
                if item.class_def is not None:
                    cls_stub = ClassStub.from_dump(item.class_def)
                    glbls[var_name] = cls_stub.load(glbls)
                elif item.function is not None:
                    fn_stub = FunctionStub.__new__(FunctionStub)
                    fn_stub.code, fn_stub.filename, fn_stub.lineno = (
                        item.function
                    )
                    glbls[var_name] = fn_stub.load(glbls)

        # Collect references to load
        ref_vars: dict[str, str] = {}
        ref_type_hints: dict[str, str | None] = {}
        variable_hashes: dict[str, str] = {}
        for var_name, item in cache_data.defs.items():
            if var_name in cache_data.ui_defs:
                ref_vars[var_name] = (base / "ui.pickle").as_posix()
            elif item.reference is not None:
                ref_vars[var_name] = item.reference
                ref_type_hints[item.reference] = item.type_hint
            if item.hash:
                variable_hashes[var_name] = item.hash

        # Eagerly resolve return value reference alongside defs
        return_ref: str | None = None
        return_type_hint: str | None = None
        if (
            cache_data.meta.return_value
            and cache_data.meta.return_value.reference
        ):
            return_ref = cache_data.meta.return_value.reference
            return_type_hint = cache_data.meta.return_value.type_hint

        unique_keys = set(ref_vars.values())
        if return_ref:
            unique_keys.add(return_ref)

        print(
            f"[lazy] restore_cache: {len(unique_keys)} blobs to fetch: "
            f"{unique_keys}"
        )

        # PASS 2: deserialize each .pickle blob through a namespace-aware
        # unpickler when `glbls` is available, so __main__ refs resolve
        # against the cell scope (PASS 1 + cells already run this kernel).
        def _deserialize_blob(key: str, data: bytes) -> Any:
            ext = Path(key).suffix
            type_hint = ref_type_hints.get(key) or (
                return_type_hint if key == return_ref else None
            )
            if ext == ".pickle" and glbls is not None:
                return pickle_load_with_namespace(data, type_hint, glbls)
            deserialize = BLOB_DESERIALIZERS.get(
                ext, BLOB_DESERIALIZERS[".pickle"]
            )
            return deserialize(data, type_hint)

        unpickled: dict[str, Any] = {}

        if isinstance(self.store, WasmExportableStore):
            # Store handles concurrency (HTTP batch in WASM,
            # sequential in native). Deserialize as each blob yields.
            for blob_key, data in self.store.get_batch(unique_keys):
                print(f"[lazy] restore_cache: blob {blob_key} -> {len(data) if data else 'None'} bytes")
                if not data:
                    raise FileNotFoundError("Incomplete cache: missing blobs")
                unpickled[blob_key] = _deserialize_blob(blob_key, data)
                print(f"[lazy] restore_cache: deserialized {blob_key} -> {type(unpickled[blob_key]).__name__}")
        else:
            # Read + deserialize in parallel via threads.
            # Every thread unconditionally puts exactly one item — either
            # the deserialized value or _BlobStatus.MISSING — so
            # queue.get() needs no timeout.
            results: queue.Queue[tuple[str, Any]] = queue.Queue()

            def _load_blob(key: str) -> None:
                try:
                    data = self.store.get(key)
                    if data:
                        results.put((key, _deserialize_blob(key, data)))
                    else:
                        results.put((key, _BlobStatus.MISSING))
                except Exception as e:
                    LOGGER.warning(
                        "Failed to deserialize blob %s: %s", key, e
                    )
                    results.put((key, _BlobStatus.MISSING))

            threads = [
                threading.Thread(target=_load_blob, args=(key,))
                for key in unique_keys
            ]
            for t in threads:
                t.start()

            # N threads → N results guaranteed; no timeout needed.
            try:
                for _ in unique_keys:
                    key, val = results.get()
                    if val is _BlobStatus.MISSING:
                        raise FileNotFoundError(
                            "Incomplete cache: missing blobs"
                        )
                    unpickled[key] = val
            finally:
                for t in threads:
                    t.join()

        # Distribute to defs
        defs: dict[str, Any] = {}
        for var_name, item in cache_data.defs.items():
            if var_name in ref_vars:
                ref_key = ref_vars[var_name]
                val = unpickled.get(ref_key)
                if var_name in cache_data.ui_defs and isinstance(val, dict):
                    defs[var_name] = val[var_name]
                else:
                    defs[var_name] = val
            else:
                defs[var_name] = from_item(item)

        if return_ref and return_ref in unpickled:
            return_item = unpickled[return_ref]
        elif cache_data.meta.return_value:
            return_item = from_item(cache_data.meta.return_value)
        else:
            return_item = None

        return Cache(
            hash=cache_data.hash,
            cache_type=cache_data.cache_type.value,
            stateful_refs=set(cache_data.stateful_refs),
            defs=defs,
            meta={
                "version": cache_data.meta.version or MARIMO_CACHE_VERSION,
                "return": return_item,
                "variable_hashes": variable_hashes,
            },
            hit=True,
        )

    def save_cache(self, cache: Cache) -> bool:
        # Reap completed threads
        self._pending = [t for t in self._pending if t.is_alive()]

        if is_pyodide():
            print(f"[lazy] save_cache: WASM sync path, hash={cache.hash}")
            result = self._save_cache_sync(cache)
            # Fresh data was written — un-poison those keys so
            # subsequent loads use the DictStore data.
            if result and isinstance(self.store, LazyStore):
                _POISONED_KEYS.clear()
                print(f"[lazy] save_cache: DictStore keys after save: {sorted(self.store._inner._data.keys()) if hasattr(self.store._inner, '_data') else 'N/A'}")
            return result

        path = Path(self.name) / cache.hash
        variable_hashes = cache.meta.get("variable_hashes", {})
        return_item = to_item(
            path, cache.meta.get("return", None), var_name="return"
        )
        if return_item.reference:
            # Normalize base name to "return" while preserving format extension.
            ext = Path(return_item.reference).suffix
            return_item.reference = (path / f"return{ext}").as_posix()

        try:
            cache_type_enum = CacheType(cache.cache_type)
        except ValueError:
            cache_type_enum = CacheType.UNKNOWN

        # Separate vars by loader strategy
        format_vars: dict[str, dict[str, Any]] = {}  # loader → {var: obj}
        ui_vars: dict[str, Any] = {}
        defs_dict: dict[str, Item] = {}
        ui_defs_list: list[str] = []

        for var, obj in cache.defs.items():
            loader = maybe_update_lazy_stub(obj)
            if loader == "ui":
                ui_vars[var] = obj
                ui_defs_list.append(var)
            elif loader not in ("inline",):
                format_vars.setdefault(loader, {})[var] = obj
            defs_dict[var] = to_item(
                path,
                obj,
                var_name=var,
                loader=loader,
                hash=variable_hashes.get(var, ""),
            )

        manifest = msgspec.json.encode(
            CacheSchema(
                hash=cache.hash,
                cache_type=cache_type_enum,
                stateful_refs=list(cache.stateful_refs),
                defs=defs_dict,
                meta=Meta(
                    version=cache.meta.get("version", MARIMO_CACHE_VERSION),
                    return_value=return_item,
                ),
                ui_defs=ui_defs_list,
            )
        )

        # Capture values for the background thread
        store = self.store
        return_ref = return_item.reference
        return_value = cache.meta.get("return", None)
        return_loader = (
            maybe_update_lazy_stub(return_value)
            if return_value is not None
            else "pickle"
        )
        manifest_key = str(self.build_path(cache.key))

        def _put_or_unhashable(
            key: str,
            value: Any,
            serialize: Callable[[Any], bytes],
            var_name: str = "",
        ) -> None:
            """Serialize and store one blob; on failure, write an
            UnhashableStub pickle to the same path so subsequent loads can
            surface a clear error rather than finding nothing."""
            try:
                store.put(key, serialize(value))
            except Exception as e:
                LOGGER.warning(
                    "Failed to serialize %s for cache; "
                    "writing UnhashableStub: %s",
                    var_name or key,
                    e,
                )
                stub = UnhashableStub(
                    value, var_name=var_name, error_msg=str(e)
                )
                try:
                    store.put(key, pickle.dumps(stub))
                except Exception:
                    LOGGER.exception(
                        "Failed to write UnhashableStub for %s",
                        var_name or key,
                    )

        def _serialize_and_write() -> None:
            """Serialize and write all blobs + manifest in background."""
            try:
                if return_ref:
                    serialize = BLOB_SERIALIZERS.get(
                        return_loader, pickle.dumps
                    )
                    _put_or_unhashable(
                        return_ref, return_value, serialize, "return"
                    )
                if ui_vars:
                    _put_or_unhashable(
                        (path / "ui.pickle").as_posix(),
                        ui_vars,
                        pickle.dumps,
                        "ui",
                    )
                for loader, vars_dict in format_vars.items():
                    serialize = BLOB_SERIALIZERS.get(loader, pickle.dumps)
                    for var, obj in vars_dict.items():
                        _put_or_unhashable(
                            (path / f"{var}.{loader}").as_posix(),
                            obj,
                            serialize,
                            var,
                        )
                # Manifest last — readers check for it to detect complete writes
                store.put(manifest_key, manifest)
            except Exception:
                LOGGER.exception("Failed to write cache manifest for %s", path)

        t = threading.Thread(target=_serialize_and_write, daemon=False)
        t.start()
        self._pending.append(t)
        return True

    def _save_cache_sync(self, cache: Cache) -> bool:
        """Write cache blobs synchronously (for WASM where threads are unavailable)."""
        path = Path(self.name) / cache.hash
        variable_hashes = cache.meta.get("variable_hashes", {})
        return_item = to_item(
            path, cache.meta.get("return", None), var_name="return"
        )
        if return_item.reference:
            ext = Path(return_item.reference).suffix
            return_item.reference = (path / f"return{ext}").as_posix()

        try:
            cache_type_enum = CacheType(cache.cache_type)
        except ValueError:
            cache_type_enum = CacheType.UNKNOWN

        format_vars: dict[str, dict[str, Any]] = {}
        ui_vars: dict[str, Any] = {}
        defs_dict: dict[str, Item] = {}
        ui_defs_list: list[str] = []

        for var, obj in cache.defs.items():
            loader = maybe_update_lazy_stub(obj)
            if loader == "ui":
                ui_vars[var] = obj
                ui_defs_list.append(var)
            elif loader not in ("inline",):
                format_vars.setdefault(loader, {})[var] = obj
            defs_dict[var] = to_item(
                path, obj, var_name=var, loader=loader,
                hash=variable_hashes.get(var, ""),
            )

        manifest = msgspec.json.encode(
            CacheSchema(
                hash=cache.hash,
                cache_type=cache_type_enum,
                stateful_refs=list(cache.stateful_refs),
                defs=defs_dict,
                meta=Meta(
                    version=cache.meta.get("version", MARIMO_CACHE_VERSION),
                    return_value=return_item,
                ),
                ui_defs=ui_defs_list,
            )
        )

        store = self.store
        try:
            if return_item.reference:
                return_value = cache.meta.get("return", None)
                return_loader = (
                    maybe_update_lazy_stub(return_value)
                    if return_value is not None
                    else "pickle"
                )
                serialize = BLOB_SERIALIZERS.get(return_loader, pickle.dumps)
                store.put(return_item.reference, serialize(return_value))
            if ui_vars:
                store.put(
                    (path / "ui.pickle").as_posix(), pickle.dumps(ui_vars)
                )
            for loader, vars_dict in format_vars.items():
                serialize = BLOB_SERIALIZERS.get(loader, pickle.dumps)
                for var, obj in vars_dict.items():
                    store.put(
                        (path / f"{var}.{loader}").as_posix(), serialize(obj)
                    )
            store.put(str(self.build_path(cache.key)), manifest)
        except Exception:
            LOGGER.exception("Failed to write cache blobs for %s", path)
            return False

        LOGGER.debug("Saved lazy cache synchronously for %s", path)
        return True

    def to_blob(self, cache: Cache) -> bytes | None:
        # Not used — save_cache is overridden. Kept for interface compliance.
        del cache
        return None
