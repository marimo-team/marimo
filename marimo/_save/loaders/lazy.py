# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import queue
import threading
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
    value: Optional[Any],
    var_name: str = "",
    loader: Optional[str] = None,
    hash: Optional[str] = "",  # noqa: A002
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
        return ImmediateReferenceStub(ReferenceStub(item.reference, item.hash))
    if item.module is not None:
        stub = ModuleStub.__new__(ModuleStub)
        stub.name = item.module
        return stub
    if item.function is not None:
        stub = FunctionStub.__new__(FunctionStub)
        stub.code, stub.filename, stub.lineno = item.function
        return stub
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

        # Read + unpickle in parallel, stream results via queue
        results: queue.Queue[tuple[str, Any]] = queue.Queue()
        unique_keys = set(ref_vars.values())

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

        return_item = (
            from_item(cache_data.meta.return_value)
            if cache_data.meta.return_value
            else None
        )

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
            if return_ref:
                store.put(return_ref, pickle.dumps(return_value))
            if ui_vars:
                store.put(
                    (path / "ui.pickle").as_posix(), pickle.dumps(ui_vars)
                )
            for var, obj in pickle_vars.items():
                store.put(
                    (path / f"{var}.pickle").as_posix(), pickle.dumps(obj)
                )
            # Manifest last — readers check for it to detect complete writes
            store.put(manifest_key, manifest)

        t = threading.Thread(target=_serialize_and_write, daemon=False)
        t.start()
        self._pending.append(t)
        return True

    def to_blob(self, cache: Cache) -> Optional[bytes]:
        # Not used — save_cache is overridden. Kept for interface compliance.
        del cache
        return None
