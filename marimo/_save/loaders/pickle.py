# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pickle
from typing import TYPE_CHECKING, Any

from marimo._save.cache import Cache
from marimo._save.loaders.loader import BasePersistenceLoader, LoaderError

if TYPE_CHECKING:
    from marimo._save.hash import HashKey


class PickleLoader(BasePersistenceLoader):
    """General loader for serializable objects."""

    def __init__(self, name: str, save_path: str, **kwargs: Any) -> None:
        super().__init__(name, "pickle", save_path, **kwargs)

    def restore_cache(self, key: HashKey, blob: bytes) -> Cache:
        del key
        cache = pickle.loads(blob)
        if not isinstance(cache, Cache):
            raise LoaderError(f"Excepted cache object, got{type(cache)}")
        return cache

    def to_blob(self, cache: Cache) -> bytes:
        return pickle.dumps(cache, protocol=pickle.HIGHEST_PROTOCOL)
