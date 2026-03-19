# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import threading
from pathlib import Path
from typing import Any, Optional

import msgspec

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

    # Primitive values stored directly
    if isinstance(value, (int, str, float, bool, bytes, type(None))):
        return Item(primitive=value)

    # Default to per-variable pickle reference
    return Item(
        reference=(path / f"{var_name}.pickle").as_posix(), hash=hash
    )


def from_item(item: Item) -> Any:
    if item.reference is not None:
        return ImmediateReferenceStub(
            ReferenceStub(item.reference, item.hash)
        )
    elif item.module is not None:
        module_stub = ModuleStub.__new__(ModuleStub)
        module_stub.name = item.module
        return module_stub
    elif item.function is not None:
        function_stub = FunctionStub.__new__(FunctionStub)
        (
            function_stub.code,
            function_stub.filename,
            function_stub.lineno,
        ) = item.function
        return function_stub
    elif item.primitive is not None:
        return item.primitive
    return None


class LazyStore(FileStore):
    ...


class LazyLoader(BasePersistenceLoader):
    def __init__(
        self,
        name: str,
        store: Optional[Store] = None,
    ) -> None:
        if store is None:
            store = LazyStore()
        super().__init__(name, "jsonl", store)

    def restore_cache(self, _key: HashKey, blob: bytes) -> Cache:
        defs = {}
        variable_hashes = {}
        cache_data = msgspec.json.decode(blob, type=CacheSchema)

        # Eagerly load shared UI blob once
        ui_blob = self.store.get(
            (Path(self.name) / cache_data.hash / "ui.pickle").as_posix()
        )
        ui_data = {}
        if cache_data.ui_defs and ui_blob is not None:
            ui_data = pickle.loads(ui_blob)

        for var_name, item in cache_data.defs.items():
            if var_name in cache_data.ui_defs:
                defs[var_name] = ui_data[var_name]
            else:
                defs[var_name] = from_item(item)

            if item.hash:
                variable_hashes[var_name] = item.hash

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

        # Per-variable pickle items
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

        schema = CacheSchema(
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
        manifest = msgspec.json.encode(schema)

        # Capture references for the background thread
        return_ref = return_item.reference
        return_value = cache.meta.get("return", None)
        manifest_key = str(self.build_path(cache.key))

        def _serialize_and_write() -> None:
            """Serialize and write all blobs + manifest.

            Writes directly (not via store.put) since we're already
            in a background thread — avoids spawning nested threads.
            """
            save = self.store.save_path

            def _write(key: str, data: bytes) -> None:
                p = save / key
                p.parent.mkdir(parents=True, exist_ok=True)
                FileStore._do_write(p, data)

            if return_ref:
                _write(return_ref, pickle.dumps(return_value))
            if ui_vars:
                _write((path / "ui.pickle").as_posix(), pickle.dumps(ui_vars))
            # Per-variable pickle files
            for var, obj in pickle_vars.items():
                _write((path / f"{var}.pickle").as_posix(), pickle.dumps(obj))
            _write(manifest_key, manifest)

        # Run serialization + writes in a background thread
        if isinstance(self.store, FileStore):
            t = threading.Thread(
                target=_serialize_and_write,
                daemon=False,
            )
            t.start()
            self.store._pending.append(t)
        else:
            _serialize_and_write()

        return True

    def to_blob(self, cache: Cache) -> Optional[bytes]:
        # Not used — save_cache is overridden. Kept for interface compliance.
        del cache
        return None
