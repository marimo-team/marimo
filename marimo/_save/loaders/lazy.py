# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import pickle
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
    path: Path, value: Optional[Any], loader: Optional[str] = None
) -> Item:
    if value is None:
        # If the value is None, we store it as an empty item
        return Item()

    if loader is None:
        loader = LAZY_STUB_LOOKUP.get(type(value), "pickle")

    if loader == "pickle":
        return Item(reference=(path / "pickles.pickle").as_posix())
    if loader == "ui":
        return Item(reference=(path / "ui.pickle").as_posix())
    if loader == "unhashable":
        # For UnhashableStub, store the type and error info
        from marimo._save.stubs.lazy_stub import UnhashableStub

        if isinstance(value, UnhashableStub):
            return Item(
                unhashable={
                    "type": value.type_name,
                    "error": value.error_msg,
                    "var_name": value.var_name,
                }
            )

    if isinstance(value, FunctionStub):
        # If the value is a FunctionStub, store the code
        return Item(function=value.dump())
    if isinstance(value, ModuleStub):
        # If the value is a ModuleStub, store the module name
        return Item(module=value.name)

    # For primitive values, store them directly
    if isinstance(value, (int, str, float, bool, bytes, type(None))):
        return Item(primitive=value)

    # For other types, use reference
    return Item(reference=(path / "pickles.pickle").as_posix())


def from_item(item: Item) -> Any:
    # Check which field is set (mimicking protobuf oneof behavior)
    if item.reference is not None:
        # If the item is a reference, we don't need to load it
        return ReferenceStub(item.reference)
    elif item.unhashable is not None:
        # Reconstruct UnhashableStub from stored metadata
        from marimo._save.stubs.lazy_stub import UnhashableStub

        # Create a dummy object with the right type name for display
        stub = UnhashableStub.__new__(UnhashableStub)
        stub.type_name = item.unhashable.get("type", "Unknown")
        stub.error_msg = item.unhashable.get("error", "Unknown error")
        stub.var_name = item.unhashable.get("var_name", "")
        stub.obj_type = type(
            None
        )  # Placeholder since we don't have the object
        return stub
    elif item.module is not None:
        module_stub = ModuleStub.__new__(ModuleStub)
        module_stub.name = item.module
        return module_stub
    elif item.function is not None:
        function_stub = FunctionStub.__new__(FunctionStub)
        function_stub.filename, function_stub.code, function.linenumber = (
            item.function
        )  # type: ignore[attr-defined]
        return function_stub
    elif item.primitive is not None:
        # Direct primitive value
        return item.primitive
    return None


# There's nothing the lazy store has over the file store for now...
class LazyStore(FileStore): ...


class LazyLoader(BasePersistenceLoader):
    def __init__(
        self,
        name: str,
        store: Optional[Store] = None,
    ) -> None:
        if store is None:
            store = LazyStore()
        super().__init__(name, "txtpb", store)
        self._loaders: dict[str, type[BasePersistenceLoader]] = {}

    def restore_cache(self, _key: HashKey, blob: bytes) -> Cache:
        defs = {}
        # Decode msgspec JSON
        cache_data = msgspec.json.decode(blob, type=CacheSchema)

        ui_blob = self.store.get(
            (Path(self.name) / cache_data.hash / "ui.pickle").as_posix()
        )
        if cache_data.ui_defs and ui_blob is not None:
            ui_data = pickle.loads(ui_blob)
        # if the item is a reference, just put in a stub
        for var_name, item in cache_data.defs.items():
            if var_name in cache_data.ui_defs:
                # If the item is a UI element, we need to handle it differently
                defs[var_name] = ui_data[var_name]
            else:
                defs[var_name] = from_item(item)

            # We do need to check that the item at leasts exists
            if isinstance(defs[var_name], ReferenceStub):
                assert self.store.hit(defs[var_name].name), (
                    f"Invalid cache reference: {defs[var_name].name}"
                )

        return_item = (
            from_item(cache_data.meta.return_value)
            if cache_data.meta.return_value
            else None
        )
        if isinstance(return_item, ReferenceStub):
            # If the return item is a reference, we need to load it
            return_item = ImmediateReferenceStub(return_item)

        return Cache(
            hash=cache_data.hash,
            cache_type=cache_data.cache_type.value,  # Convert enum to string
            stateful_refs=set(cache_data.stateful_refs),
            defs=defs,
            meta={
                "version": cache_data.meta.version or MARIMO_CACHE_VERSION,
                "return": return_item,
            },
            hit=True,
        )

        # self._loader._save_path = self._save_path
        # cache = self._loader.load_persistent_cache(hashed_context, cache_type)
        # for loader, defs in cache.defs.items():
        #     obj_cache = PERSISTENT_LOADERS[loader](loader, self.save_path).load(
        #         hashed_context, cache_type
        #     )
        #     cache.update(obj_cache)
        #     # Check defs actually loaded
        #     assert defs == cache.defs.keys()
        # return cache

    def to_blob(self, cache: Cache) -> bytes:
        collections: dict[str, dict[str, Any]] = {}
        path = Path(self.name) / cache.hash  # / "lazy"
        return_item = to_item(path, cache.meta.get("return", None))
        if return_item.reference:
            return_item.reference = (path / "return.pickle").as_posix()

        # Convert cache_type string back to enum
        try:
            cache_type_enum = CacheType(cache.cache_type)
        except ValueError:
            cache_type_enum = CacheType.UNKNOWN

        defs_dict = {}
        ui_defs_list = []

        for var, obj in cache.defs.items():
            loader = LAZY_STUB_LOOKUP.get(type(obj), "pickle")

            # For pickle loader, verify the object can actually be pickled
            if loader == "pickle":
                try:
                    pickle.dumps(obj)
                except (pickle.PicklingError, TypeError, AttributeError) as e:
                    # Cannot pickle - create UnhashableStub for graceful degradation
                    from marimo._save.stubs.lazy_stub import UnhashableStub

                    obj = UnhashableStub(obj, e, var_name=var)
                    loader = "unhashable"

            # txtpb is handled directly in the serialized blob, so no point
            # registering it in the collection.
            if loader != "txtpb":
                collection = collections.get(loader, {})
                collection[var] = obj
                collections[loader] = collection
            if loader == "ui":
                ui_defs_list.append(var)
            defs_dict[var] = to_item(path, obj, loader)

        store = CacheSchema(
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

        # Handle return value separately
        if return_item.reference:
            try:
                blob = pickle.dumps(cache.meta.get("return", None))
                self.store.put(return_item.reference, blob)
            except (pickle.PicklingError, TypeError, AttributeError) as e:
                # Return value can't be pickled - replace with UnhashableStub
                from marimo._save.stubs.lazy_stub import UnhashableStub

                return_stub = UnhashableStub(
                    cache.meta.get("return", None), e, var_name="<return>"
                )
                # Update the return_item to be unhashable
                return_item = Item(
                    unhashable={
                        "type": return_stub.type_name,
                        "error": return_stub.error_msg,
                        "var_name": return_stub.var_name,
                    }
                )
                # Update store with new return_item
                store.meta = Meta(
                    version=cache.meta.get("version", MARIMO_CACHE_VERSION),
                    return_value=return_item,
                )

        # Handle ui elements separately
        ui = collections.get("ui", {})
        if ui:
            blob = pickle.dumps(ui)
            ui_path = path / "ui.pickle"
            self.store.put(ui_path.as_posix(), blob)
            # Dump to shared pickle object
        pickles = collections.get("pickle", {})
        if pickles:
            blob = pickle.dumps(pickles)
            pickles_path = path / "pickles.pickle"
            self.store.put(pickles_path.as_posix(), blob)
            # Dump to shared pickle object

        return msgspec.json.encode(store)

        # TODO: Spawn loaders for each collection and save them async.
        # for loader, collection in collections.items():
        #     if loader not in self._loaders:
        #         self._loaders[loader] = PERSISTENT_LOADERS[loader](self.name, self._store)
        #     # Actually save
        #     # self._loaders[loader].to_blob(Cache(collection))
        # self._loader.save_cache(Cache(stubs))
