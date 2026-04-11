# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import queue
import threading
from pathlib import Path
from typing import Any

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
    LAZY_STUB_LOOKUP,
    FunctionStub,
    ModuleStub,
)
from marimo._save.stubs.lazy_stub import (
    Cache as CacheSchema,
    CacheType,
    ImmediateReferenceStub,
    Item,
    Meta,
    ReferenceStub,
)

LOGGER = _loggers.marimo_logger()


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
        loader = LAZY_STUB_LOOKUP.get(type(value), "pickle")

    if loader == "pickle":
        return Item(
            reference=(path / f"{var_name}.pickle").as_posix(), hash=hash
        )
    if loader == "ui":
        return Item(reference=(path / "ui.pickle").as_posix())
    if isinstance(value, FunctionStub):
        return Item(function=value.dump())
    if isinstance(value, ModuleStub):
        return Item(module=value.name)
    if isinstance(value, (int, str, float, bool, bytes, type(None))):
        return Item(primitive=value)

    return Item(reference=(path / f"{var_name}.pickle").as_posix(), hash=hash)


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
        store: Store | None = None,
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

    def load_cache(self, key: HashKey) -> Cache | None:
        try:
            blob: bytes | None = self.store.get(str(self.build_path(key)))
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
        variable_hashes: dict[str, str] = {}
        for var_name, item in cache_data.defs.items():
            if var_name in cache_data.ui_defs:
                ref_vars[var_name] = (base / "ui.pickle").as_posix()
            elif item.reference is not None:
                ref_vars[var_name] = item.reference
            if item.hash:
                variable_hashes[var_name] = item.hash

        # Eagerly resolve return value reference alongside defs
        return_ref: str | None = None
        if (
            cache_data.meta.return_value
            and cache_data.meta.return_value.reference
        ):
            return_ref = cache_data.meta.return_value.reference

        # Read + unpickle in parallel, stream results via queue
        results: queue.Queue[tuple[str, Any]] = queue.Queue()
        unique_keys = set(ref_vars.values())
        if return_ref:
            unique_keys.add(return_ref)

        def _load_and_unpickle(key: str) -> None:
            data = self.store.get(key)
            if data:
                results.put((key, pickle.loads(data)))

        threads = [
            threading.Thread(target=_load_and_unpickle, args=(key,))
            for key in unique_keys
        ]
        for t in threads:
            t.start()

        # Stream results as they arrive
        unpickled: dict[str, Any] = {}
        for _ in unique_keys:
            try:
                key, val = results.get(timeout=30)
                unpickled[key] = val
            except queue.Empty:
                break

        for t in threads:
            t.join()

        if len(unpickled) < len(unique_keys):
            raise FileNotFoundError("Incomplete cache: missing blobs")

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
            return_item.reference = (path / "return.pickle").as_posix()

        try:
            cache_type_enum = CacheType(cache.cache_type)
        except ValueError:
            cache_type_enum = CacheType.UNKNOWN

        pickle_vars: dict[str, Any] = {}
        ui_vars: dict[str, Any] = {}
        defs_dict: dict[str, Item] = {}
        ui_defs_list: list[str] = []

        for var, obj in cache.defs.items():
            loader = LAZY_STUB_LOOKUP.get(type(obj), "pickle")
            if loader == "pickle":
                pickle_vars[var] = obj
            elif loader == "ui":
                ui_vars[var] = obj
                ui_defs_list.append(var)
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
        manifest_key = str(self.build_path(cache.key))

        def _serialize_and_write() -> None:
            """Serialize and write all blobs + manifest in background."""
            try:
                if return_ref:
                    store.put(return_ref, pickle.dumps(return_value))
                if ui_vars:
                    store.put(
                        (path / "ui.pickle").as_posix(),
                        pickle.dumps(ui_vars),
                    )
                for var, obj in pickle_vars.items():
                    store.put(
                        (path / f"{var}.pickle").as_posix(),
                        pickle.dumps(obj),
                    )
                # Manifest last — readers check for it to detect complete writes
                store.put(manifest_key, manifest)
            except Exception:
                LOGGER.exception("Failed to write cache blobs for %s", path)

        t = threading.Thread(target=_serialize_and_write, daemon=False)
        t.start()
        self._pending.append(t)
        return True

    def to_blob(self, cache: Cache) -> bytes | None:
        # Not used — save_cache is overridden. Kept for interface compliance.
        del cache
        return None
