# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import queue
import threading
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import msgspec

from marimo import _loggers
from marimo._save.cache import (
    MARIMO_CACHE_VERSION,
    Cache,
)
from marimo._save.hash import HashKey
from marimo._save.loaders.loader import BasePersistenceLoader
from marimo._save.stores import FileStore, Store
from marimo._save.stubs import (
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
)
from marimo._save.stubs.stubs import mro_lookup

LOGGER = _loggers.marimo_logger()


class _BlobStatus(Enum):
    """Sentinel placed in the results queue when a blob is missing."""

    MISSING = auto()


def maybe_update_lazy_stub(value: Any) -> str:
    """Return the loader strategy string for *value*, caching the result.

    Walks the MRO of ``type(value)`` against ``LAZY_STUB_LOOKUP`` (a
    fq-class-name → loader-string registry).  Falls back to ``"pickle"``
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
    value: Optional[Any],
    var_name: str = "",
    loader: Optional[str] = None,
    hash: Optional[str] = "",  # noqa: A002
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
    if isinstance(value, ModuleStub):
        return Item(module=value.name)
    if isinstance(value, (int, str, float, bool, bytes, type(None))):
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
    if item.primitive is not None:
        return item.primitive
    return None


class LazyStore(FileStore): ...


class LazyLoader(BasePersistenceLoader):
    def __init__(
        self,
        name: str,
        store: Optional[Store] = None,
    ) -> None:
        if store is None:
            store = LazyStore()
        super().__init__(name, "jsonl", store)
        self._pending: list[threading.Thread] = []

    def flush(self) -> None:
        """Wait for all pending background writes to complete."""
        for t in self._pending:
            t.join()
        self._pending.clear()

    def load_cache(self, key: HashKey) -> Optional[Cache]:
        try:
            blob: Optional[bytes] = self.store.get(str(self.build_path(key)))
            if not blob:
                return None
            return self.restore_cache(key, blob)
        except Exception as e:
            LOGGER.warning("Failed to restore lazy cache: %s", e)
            return None

    def restore_cache(self, _key: HashKey, blob: bytes) -> Cache:
        cache_data = msgspec.json.decode(blob, type=CacheSchema)
        base = Path(self.name) / cache_data.hash

        # Collect references to load
        ref_vars: dict[str, str] = {}
        ref_type_hints: dict[str, Optional[str]] = {}
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
        return_ref: Optional[str] = None
        return_type_hint: Optional[str] = None
        if (
            cache_data.meta.return_value
            and cache_data.meta.return_value.reference
        ):
            return_ref = cache_data.meta.return_value.reference
            return_type_hint = cache_data.meta.return_value.type_hint

        # Read + deserialize in parallel, stream results via queue.
        # Every thread unconditionally puts exactly one item — either the
        # deserialized value or _BlobStatus.MISSING — so queue.get() needs
        # no timeout.
        results: queue.Queue[tuple[str, Any]] = queue.Queue()
        unique_keys = set(ref_vars.values())
        if return_ref:
            unique_keys.add(return_ref)

        def _load_blob(key: str) -> None:
            try:
                data = self.store.get(key)
                if data:
                    ext = Path(key).suffix
                    deserialize = BLOB_DESERIALIZERS.get(
                        ext, BLOB_DESERIALIZERS[".pickle"]
                    )
                    type_hint = ref_type_hints.get(key) or (
                        return_type_hint if key == return_ref else None
                    )
                    results.put((key, deserialize(data, type_hint)))
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

        # N threads → N results guaranteed; no timeout needed.
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

        def _serialize_and_write() -> None:
            """Serialize and write all blobs + manifest in background."""
            try:
                if return_ref:
                    serialize = BLOB_SERIALIZERS.get(
                        return_loader, pickle.dumps
                    )
                    store.put(return_ref, serialize(return_value))
                if ui_vars:
                    store.put(
                        (path / "ui.pickle").as_posix(),
                        pickle.dumps(ui_vars),
                    )
                for loader, vars_dict in format_vars.items():
                    serialize = BLOB_SERIALIZERS.get(loader, pickle.dumps)
                    for var, obj in vars_dict.items():
                        store.put(
                            (path / f"{var}.{loader}").as_posix(),
                            serialize(obj),
                        )
                # Manifest last — readers check for it to detect complete writes
                store.put(manifest_key, manifest)
            except Exception:
                LOGGER.exception("Failed to write cache blobs for %s", path)

        t = threading.Thread(target=_serialize_and_write, daemon=False)
        t.start()
        self._pending.append(t)
        return True

    def to_blob(self, cache: Cache) -> Optional[bytes]:
        # Not used — save_cache is overridden. Kept for interface compliance.
        del cache
        return None
