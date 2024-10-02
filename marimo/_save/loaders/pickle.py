# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import pickle
from pathlib import Path

from marimo._save.cache import CACHE_PREFIX, Cache, CacheType
from marimo._save.loaders.loader import INCONSISTENT_CACHE_BOILER_PLATE, Loader


class PickleLoader(Loader):
    """General loader for serializable objects."""

    def __init__(self, name: str, save_path: str) -> None:
        super().__init__(name)
        self.name = name
        self.save_path = Path(save_path) / name
        self.save_path.mkdir(parents=True, exist_ok=True)

    def build_path(self, hashed_context: str, cache_type: CacheType) -> Path:
        prefix = CACHE_PREFIX.get(cache_type, "U_")
        return self.save_path / f"{prefix}{hashed_context}.pickle"

    def cache_hit(self, hashed_context: str, cache_type: CacheType) -> bool:
        path = self.build_path(hashed_context, cache_type)
        return os.path.exists(path) and os.path.getsize(path) > 0

    def load_cache(self, hashed_context: str, cache_type: CacheType) -> Cache:
        assert self.cache_hit(
            hashed_context, cache_type
        ), INCONSISTENT_CACHE_BOILER_PLATE
        with open(self.build_path(hashed_context, cache_type), "rb") as handle:
            cache = pickle.load(handle)
            assert isinstance(cache, Cache), (
                "Excepted cache object, got" f"{type(cache)} ",
                INCONSISTENT_CACHE_BOILER_PLATE,
            )
            return cache

    def save_cache(self, cache: Cache) -> None:
        with open(self.build_path(cache.hash, cache.cache_type), "wb") as f:
            pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
