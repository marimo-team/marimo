# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import importlib
import inspect
import pickle
import queue
import threading
from enum import Enum, auto
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import msgspec

from marimo import _loggers
from marimo._save.cache import (
    MARIMO_CACHE_VERSION,
    Cache,
)
from marimo._save.hash import HashKey
from marimo._save.loaders.loader import BasePersistenceLoader
from marimo._save.stores import FileStore, Store
from marimo._save.stores.store import WasmExportableStore

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
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

if TYPE_CHECKING:
    from collections.abc import Callable

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


def _maybe_import_ref(value: Any) -> tuple[str, str] | None:
    """Return `(module, qualname)` if *value* is re-importable by name,
    else `None`.
    """
    if not (
        inspect.isclass(value)
        or inspect.isroutine(value)
        or type(value).__module__ == "typing"
    ):
        return None
    module = getattr(value, "__module__", None)
    qualname = (
        getattr(value, "__qualname__", None)
        or getattr(value, "__name__", None)
        or getattr(value, "_name", None)
    )
    if not module or module == "__main__" or not qualname:
        return None
    try:
        obj: Any = importlib.import_module(module)
        for part in qualname.split("."):
            obj = getattr(obj, part)
    except (ImportError, AttributeError):
        return None
    return (module, qualname) if obj is value else None


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
        # A re-importable reference is stored inline rather than as a blob.
        ref = _maybe_import_ref(value)
        if ref is not None:
            return Item(import_ref=ref)
    if loader in ("pickle", "npy", "arrow", "pt"):
        # Blob strategies: the file extension is the loader name, matching
        # the path `save_cache` writes (`{var}.{loader}`). Listing them
        # together keeps a new format (e.g. `pt`) from silently falling
        # through to the `.pickle` fallback and mismatching its blob.
        return Item(
            reference=(path / f"{var_name}.{loader}").as_posix(),
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
    if isinstance(value, (int, str, float, bool, bytes, type(None))):
        return Item(primitive=value)

    return Item(
        reference=(path / f"{var_name}.pickle").as_posix(),
        hash=hash,
        type_hint=type_hint,
    )


def from_item(item: Item, var_name: str = "") -> Any:
    if item.unserializable_type is not None:
        # No blob was written for this def — rebuild the tripwire in-memory
        # from the manifest marker.
        return UnhashableStub(
            var_name=var_name, type_name=item.unserializable_type
        )
    if item.reference is not None:
        return ImmediateReferenceStub(
            ReferenceStub(item.reference, hash_value=item.hash or "")
        )
    if item.module is not None:
        mod_stub = ModuleStub.__new__(ModuleStub)
        mod_stub.name = item.module
        return mod_stub
    if item.import_ref is not None:
        module, qualname = item.import_ref
        obj: Any = importlib.import_module(module)
        for part in qualname.split("."):
            obj = getattr(obj, part)
        return obj
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


# Keys whose deserialization failed — never re-fetched over HTTP. Survives
# across LazyStore instances.
_POISONED_KEYS: set[str] = set()


class LazyStore(WasmExportableStore):
    """Native store for `LazyLoader`.

    Delegates to an inner store (default `FileStore` at `__marimo__/cache/`)
    and tracks which keys were written or read so `--execute` export knows
    exactly which blobs to bundle. Does no environment checks; the WASM
    variant (`WasmLazyStore`) adds HTTP-backed reads.
    """

    def __init__(self, inner: Store | None = None) -> None:
        self._inner = inner if inner is not None else FileStore()
        self._written_keys: set[str] = set()
        # Keys read this session. A warm re-export hits the cache rather
        # than re-writing it, so the export manifest must cover reads too
        # or the bundle ships incomplete.
        self._touched_keys: set[str] = set()

    def get(self, key: str) -> bytes | None:
        result = self._inner.get(key)
        if result is not None:
            self._touched_keys.add(key)
        return result

    def put(self, key: str, value: bytes) -> bool:
        self._written_keys.add(key)
        return self._inner.put(key, value)

    def hit(self, key: str) -> bool:
        result = self._inner.hit(key)
        if result:
            self._touched_keys.add(key)
        return result

    def clear(self, key: str) -> bool:
        self._written_keys.discard(key)
        self._touched_keys.discard(key)
        return self._inner.clear(key)

    def get_batch(
        self, keys: Iterable[str]
    ) -> Iterator[tuple[str, bytes | None]]:
        for k in keys:
            yield k, self.get(k)

    def export_manifest(self) -> list[str]:
        return sorted(self._written_keys | self._touched_keys)


class WasmLazyStore(LazyStore):
    """WASM store: writes to a shared in-session `DictStore`; reads fall
    through to HTTP fetch from `notebook_location()/public/cache/`.

    Instantiated only by `WasmLazyLoader` (selected once via the dual-loader
    registry), so it never needs to re-check the environment.
    """

    def __init__(self, inner: Store | None = None) -> None:
        super().__init__(
            inner if inner is not None else _get_wasm_dict_store()
        )

    def get(self, key: str) -> bytes | None:
        result = super().get(key)
        if result is not None:
            return result
        if key not in _POISONED_KEYS:
            return self._http_get(key)
        return None

    def get_batch(
        self, keys: Iterable[str]
    ) -> Iterator[tuple[str, bytes | None]]:
        # Inner store first; HTTP-fetch only the (unpoisoned) misses, fired
        # concurrently.
        http_keys: list[str] = []
        for k in keys:
            data = self._inner.get(k)
            if data is not None:
                self._touched_keys.add(k)
                yield k, data
            elif k not in _POISONED_KEYS:
                http_keys.append(k)
            else:
                yield k, None
        if http_keys:
            yield from self._http_get_batch(http_keys)

    # -- HTTP internals --

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

        from js import fetch  # type: ignore

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
            return await asyncio.gather(*(_fetch_one(k) for k in keys_list))

        try:
            results = loop.run_until_complete(_fetch_all())
        except Exception:
            # run_until_complete on the live pyodide loop requires JSPI
            # (WebAssembly stack switching), which e.g. Firefox lacks. Fall
            # back to sequential synchronous XHR via the pyodide_http-patched
            # urllib — legal in a worker.
            results = [(k, self._http_get(k)) for k in keys_list]
        yield from results


# Registry of active loaders by name, so a recreated loader reuses the same
# store (and so `flush_all`/export can reach every session loader).
_ACTIVE_LAZY_LOADERS: dict[str, LazyLoader] = {}


class LazyLoader(BasePersistenceLoader):
    # Default store class, overridden by the WASM variant. The single
    # native/WASM decision is made once in the dual-loader registry, not here.
    _store_cls: type[Store] = LazyStore

    def __init__(
        self,
        name: str,
        store: Store | None = None,
    ) -> None:
        if store is None:
            # Reuse the same store across recreations of a named loader
            # (State GC, partial reconstruction) so cached data survives.
            prev = _ACTIVE_LAZY_LOADERS.get(name)
            store = prev.store if prev is not None else self._store_cls()
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
        del glbls
        blob: bytes | None = None
        try:
            blob = self.store.get(str(self.build_path(key)))
            if not blob:
                return None
            return self.restore_cache(key, blob)
        except Exception as e:
            LOGGER.warning("Failed to restore lazy cache: %s", e)
            self._on_restore_failure(key, blob)
            return None

    def _on_restore_failure(
        self, key: HashKey, manifest_blob: bytes | None
    ) -> None:
        """Hook after a failed restore. No-op natively; the WASM variant
        evicts and poisons the bad keys so HTTP won't re-fetch them."""

    def restore_cache(self, _key: HashKey, blob: bytes) -> Cache:
        cache_data = msgspec.json.decode(blob, type=CacheSchema)
        base = Path(self.name) / cache_data.hash

        # Collect references to load
        ref_vars: dict[str, str] = {}
        ref_type_hints: dict[str, str | None] = {}
        variable_hashes: dict[str, str] = {}
        # Instances of cell-defined (__main__) classes are deferred: their
        # class must be re-exec'd into __main__ before the blob can unpickle.
        # Cache.restore orders these after their class via `requires`.
        deferred: dict[str, tuple[str, str]] = {}
        for var_name, item in cache_data.defs.items():
            if var_name in cache_data.ui_defs:
                ref_vars[var_name] = (base / "ui.pickle").as_posix()
            elif item.reference is not None:
                if item.type_hint and item.type_hint.startswith("__main__."):
                    deferred[var_name] = (
                        item.reference,
                        item.type_hint.rsplit(".", 1)[-1],
                    )
                else:
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
        # Read + deserialize the blobs. The native loader parallelizes via
        # threads; the WASM loader overrides this to fetch via the store's
        # concurrent get_batch (threads are unavailable in Pyodide).
        unpickled = self._read_blobs(
            unique_keys, ref_type_hints, return_ref, return_type_hint
        )

        # Distribute to defs
        defs: dict[str, Any] = {}
        for var_name, item in cache_data.defs.items():
            if var_name in deferred:
                ref, requires = deferred[var_name]
                # Read the bytes now (via this loader's store); defer only
                # the unpickle until Cache.restore has materialized the class.
                raw = self.store.get(ref)
                if not raw:
                    raise FileNotFoundError("Incomplete cache: missing blobs")
                stub = ImmediateReferenceStub(
                    ReferenceStub(ref, hash_value=item.hash or "", blob=raw)
                )
                # Tag the cell class this instance needs materialized first.
                stub.requires = requires
                defs[var_name] = stub
            elif var_name in ref_vars:
                ref_key = ref_vars[var_name]
                val = unpickled.get(ref_key)
                if var_name in cache_data.ui_defs and isinstance(val, dict):
                    defs[var_name] = val[var_name]
                else:
                    defs[var_name] = val
            else:
                defs[var_name] = from_item(item, var_name)

        if return_ref and return_ref in unpickled:
            return_item = unpickled[return_ref]
        elif cache_data.meta.return_value:
            return_item = from_item(cache_data.meta.return_value, "return")
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

    def _deserialize_blob(
        self,
        key: str,
        data: bytes,
        ref_type_hints: dict[str, str | None],
        return_ref: str | None,
        return_type_hint: str | None,
    ) -> Any:
        ext = Path(key).suffix
        deserialize = BLOB_DESERIALIZERS.get(
            ext, BLOB_DESERIALIZERS[".pickle"]
        )
        type_hint = ref_type_hints.get(key) or (
            return_type_hint if key == return_ref else None
        )
        return deserialize(data, type_hint)

    def _read_blobs(
        self,
        unique_keys: set[str],
        ref_type_hints: dict[str, str | None],
        return_ref: str | None,
        return_type_hint: str | None,
    ) -> dict[str, Any]:
        """Read + deserialize blobs in parallel via threads.

        Every thread puts exactly one item — value or `_BlobStatus.MISSING`
        — so `queue.get()` needs no timeout. `WasmLazyLoader` overrides this
        to use the store's concurrent `get_batch` (no threads in Pyodide).
        """
        results: queue.Queue[tuple[str, Any]] = queue.Queue()

        def _load_blob(key: str) -> None:
            try:
                data = self.store.get(key)
                if data:
                    results.put(
                        (
                            key,
                            self._deserialize_blob(
                                key,
                                data,
                                ref_type_hints,
                                return_ref,
                                return_type_hint,
                            ),
                        )
                    )
                else:
                    results.put((key, _BlobStatus.MISSING))
            except Exception as e:
                LOGGER.warning("Failed to deserialize blob %s: %s", key, e)
                results.put((key, _BlobStatus.MISSING))

        threads = [
            threading.Thread(target=_load_blob, args=(key,))
            for key in unique_keys
        ]
        for t in threads:
            t.start()
        unpickled: dict[str, Any] = {}
        try:
            for _ in unique_keys:
                key, val = results.get()
                if val is _BlobStatus.MISSING:
                    raise FileNotFoundError("Incomplete cache: missing blobs")
                unpickled[key] = val
        finally:
            for t in threads:
                t.join()
        return unpickled

    def save_cache(self, cache: Cache) -> bool:
        # Reap completed threads
        self._pending = [t for t in self._pending if t.is_alive()]

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
            item = to_item(
                path,
                obj,
                var_name=var,
                loader=loader,
                hash=variable_hashes.get(var, ""),
            )
            defs_dict[var] = item
            if item.import_ref is not None:
                # Re-importable reference: lives inline in the manifest,
                # no blob to write.
                continue
            if loader == "ui":
                ui_vars[var] = obj
                ui_defs_list.append(var)
            elif loader not in ("inline",):
                format_vars.setdefault(loader, {})[var] = obj

        version = cache.meta.get("version", MARIMO_CACHE_VERSION)

        def _encode_manifest() -> bytes:
            # Encoded after the blobs so any `unserializable_type` marks set
            # by `_put_or_mark_unserializable` are reflected in the manifest.
            return msgspec.json.encode(
                CacheSchema(
                    hash=cache.hash,
                    cache_type=cache_type_enum,
                    stateful_refs=list(cache.stateful_refs),
                    defs=defs_dict,
                    meta=Meta(
                        version=version,
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

        def _put_or_mark_unserializable(
            key: str,
            value: Any,
            serialize: Callable[[Any], bytes],
            items: list[Item],
            var_name: str = "",
        ) -> bool:
            """Store one blob; on serialization failure write no blob and
            instead mark each manifest `Item` with `unserializable_type`.

            A later load reconstructs an `UnhashableStub` tripwire from the
            marker (see `from_item`) rather than reading a placeholder blob
            off disk — so unserializable values never get dumped to disk and
            the cached-execution pre-flight still re-runs the producing cell.

            Returns `True` when the blob was stored, `False` when it was
            marked unserializable.
            """
            try:
                store.put(key, serialize(value))
            except Exception as e:
                LOGGER.warning(
                    "Failed to serialize %s for cache; marking "
                    "unserializable: %s",
                    var_name or key,
                    e,
                )
                fallback = f"{type(value).__module__}.{type(value).__name__}"
                for item in items:
                    type_name = item.type_hint or fallback
                    item.reference = None
                    item.hash = None
                    item.type_hint = None
                    item.unserializable_type = type_name
                return False
            return True

        def _serialize_and_write() -> None:
            """Serialize and write all blobs + manifest in background."""
            try:
                if return_ref:
                    serialize = BLOB_SERIALIZERS.get(
                        return_loader, pickle.dumps
                    )
                    _put_or_mark_unserializable(
                        return_ref,
                        return_value,
                        serialize,
                        [return_item],
                        "return",
                    )
                if ui_vars:
                    ui_key = (path / "ui.pickle").as_posix()
                    ui_ok = _put_or_mark_unserializable(
                        ui_key,
                        ui_vars,
                        pickle.dumps,
                        [defs_dict[v] for v in ui_defs_list],
                        "ui",
                    )
                    if not ui_ok:
                        # UI defs restore via `ui_defs` → `ui.pickle`,
                        # bypassing the per-Item marks. Drop them from
                        # `ui_defs` so restore routes through the now-marked
                        # Items instead, and clear any stale blob lingering
                        # from a prior run at this same hash path (which would
                        # otherwise load as a phantom hit).
                        ui_defs_list.clear()
                        try:
                            store.clear(ui_key)
                        except Exception:
                            LOGGER.warning(
                                "Failed to clear stale ui blob %s", ui_key
                            )
                for loader, vars_dict in format_vars.items():
                    serialize = BLOB_SERIALIZERS.get(loader, pickle.dumps)
                    for var, obj in vars_dict.items():
                        _put_or_mark_unserializable(
                            (path / f"{var}.{loader}").as_posix(),
                            obj,
                            serialize,
                            [defs_dict[var]],
                            var,
                        )
                # Manifest last — readers check for it to detect complete
                # writes, and it now carries any unserializable marks set above.
                store.put(manifest_key, _encode_manifest())
            except Exception:
                LOGGER.exception("Failed to write cache blobs for %s", path)

        self._dispatch_write(_serialize_and_write)
        return True

    def _dispatch_write(self, write_fn: Callable[[], None]) -> None:
        """Run the blob+manifest write on a background thread (native).

        `WasmLazyLoader` overrides this to run synchronously, since threads
        are unavailable in Pyodide.
        """
        t = threading.Thread(target=write_fn, daemon=False)
        t.start()
        self._pending.append(t)

    def to_blob(self, cache: Cache) -> bytes | None:
        # Not used — save_cache is overridden. Kept for interface compliance.
        del cache
        return None


class WasmLazyLoader(LazyLoader):
    """WASM variant of `LazyLoader`, selected once via the dual-loader
    registry (so the environment is never re-checked below).

    - reads blobs through the store's concurrent `get_batch` (HTTP fetch in
      Pyodide) since threads are unavailable;
    - writes synchronously for the same reason;
    - on a corrupt restore, evicts the blobs and poisons their keys so the
      store won't HTTP-re-fetch the same broken data.
    """

    _store_cls = WasmLazyStore

    def _read_blobs(
        self,
        unique_keys: set[str],
        ref_type_hints: dict[str, str | None],
        return_ref: str | None,
        return_type_hint: str | None,
    ) -> dict[str, Any]:
        unpickled: dict[str, Any] = {}
        # The store handles concurrency (HTTP batch fetch in WASM). The WASM
        # variant always pairs with a WasmExportableStore (see `_store_cls`).
        store = self.store
        assert isinstance(store, WasmExportableStore)
        for key, data in store.get_batch(unique_keys):
            if not data:
                raise FileNotFoundError("Incomplete cache: missing blobs")
            unpickled[key] = self._deserialize_blob(
                key, data, ref_type_hints, return_ref, return_type_hint
            )
        return unpickled

    def _dispatch_write(self, write_fn: Callable[[], None]) -> None:
        write_fn()  # synchronous — no threads in Pyodide

    def _on_restore_failure(
        self, key: HashKey, manifest_blob: bytes | None
    ) -> None:
        manifest_path = str(self.build_path(key))
        blob_keys: list[str] = []
        if manifest_blob:
            try:
                cache_data = msgspec.json.decode(
                    manifest_blob, type=CacheSchema
                )
                for item in cache_data.defs.values():
                    if item.reference:
                        blob_keys.append(item.reference)
                if cache_data.meta.return_value and (
                    ref := cache_data.meta.return_value.reference
                ):
                    blob_keys.append(ref)
            except Exception:
                pass
        self.store.clear(manifest_path)
        _POISONED_KEYS.add(manifest_path)
        for blob_key in blob_keys:
            self.store.clear(blob_key)
            _POISONED_KEYS.add(blob_key)
