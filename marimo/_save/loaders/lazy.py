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
    FunctionStub,
    ModuleStub,
)
from marimo._save.stubs.lazy_stubs import (
    TYPE_LOOKUP,
    Cache as CacheSchema,
    CacheType,
    ImmediateReferenceStub,
    Item,
    Meta,
    ReferenceStub,
)


def to_item(path, value: Optional[Any], loader: str | None = None) -> Item:
    if value is None:
        # If the value is None, we store it as an empty item
        return Item()

    if loader is None:
        loader = TYPE_LOOKUP.get(type(value), "pickle")

    if loader == "pickle":
        return Item(reference=(path / "pickles.pickle").as_posix())
    if loader == "ui":
        return Item(reference=(path / "ui.pickle").as_posix())

    if isinstance(value, FunctionStub):
        # If the value is a FunctionStub, store the code
        return Item(function=value.code)
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
    elif item.module is not None:
        stub = ModuleStub.__new__(ModuleStub)
        stub.name = item.module
        return stub
    elif item.function is not None:
        stub = FunctionStub.__new__(FunctionStub)
        stub.code = item.function
        return stub
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

    def restore_cache(self, key: HashKey, blob: bytes) -> Cache:
        defs = {}
        # Decode msgspec JSON
        cache_data = msgspec.json.decode(blob, type=CacheSchema)

        ui_blob = self.store.get(
            Path(self.name) / cache_data.hash / "ui.pickle"
        )
        if cache_data.ui_defs:
            ui_data = pickle.loads(ui_blob)
        # if the item is a reference, just put in a stub
        for key, item in cache_data.defs.items():
            if key in cache_data.ui_defs:
                # If the item is a UI element, we need to handle it differently
                defs[key] = ui_data[key]
            else:
                defs[key] = from_item(item)

            # We do need to check that the item at leasts exists
            if isinstance(defs[key], ReferenceStub):
                assert self.store.hit(defs[key].name), (
                    f"Invalid cache reference: {defs[key].name}"
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
            stateful_refs=cache_data.stateful_refs,
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
        collections = {}
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
            loader = TYPE_LOOKUP.get(type(obj), "pickle")
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
            stateful_refs=cache.stateful_refs,
            defs=defs_dict,
            meta=Meta(
                version=cache.meta.get("version", MARIMO_CACHE_VERSION),
                return_value=return_item,
            ),
            ui_defs=ui_defs_list,
        )

        # Handle return value separately
        if return_item.reference:
            blob = pickle.dumps(cache.meta.get("return", None))
            self.store.put(return_item.reference, blob)

        # Handle ui elements separately
        ui = collections.get("ui", {})
        if ui:
            blob = pickle.dumps(ui)
            ui_path = path / "ui.pickle"
            self.store.put(ui_path, blob)
            # Dump to shared pickle object
        pickles = collections.get("pickle", {})
        if pickles:
            blob = pickle.dumps(pickles)
            pickles_path = path / "pickles.pickle"
            self.store.put(pickles_path, blob)
            # Dump to shared pickle object

        return msgspec.json.encode(store)

        # TODO: Spawn loaders for each collection and save them async.
        # for loader, collection in collections.items():
        #     if loader not in self._loaders:
        #         self._loaders[loader] = PERSISTENT_LOADERS[loader](self.name, self._store)
        #     # Actually save
        #     # self._loaders[loader].to_blob(Cache(collection))
        # self._loader.save_cache(Cache(stubs))
