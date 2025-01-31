# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pickle

from marimo._save.cache import Cache, CacheType
from marimo._save.loaders.loader import BasePersistenceLoader, LoaderError


class PickleLoader(BasePersistenceLoader):
    """General loader for serializable objects."""

    def __init__(self, name: str, save_path: str) -> None:
        super().__init__(name, "pickle", save_path)

    def load_persistent_cache(
        self, hashed_context: str, cache_type: CacheType
    ) -> Cache:
        with open(self.build_path(hashed_context, cache_type), "rb") as handle:
            cache = pickle.load(handle)
            if not isinstance(cache, Cache):
                raise LoaderError(f"Excepted cache object, got{type(cache)}")
            return cache

    def save_cache(self, cache: Cache) -> None:
        with open(self.build_path(cache.hash, cache.cache_type), "wb") as f:
            pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
