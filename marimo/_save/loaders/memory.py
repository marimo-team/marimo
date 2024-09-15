# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Optional

from marimo._save.cache import Cache, CacheType
from marimo._save.loaders.loader import INCONSISTENT_CACHE_BOILER_PLATE, Loader

if TYPE_CHECKING:
    from pathlib import Path


class MemoryLoader(Loader):
    """In memory loader for serializable objects."""

    def __init__(
        self,
        *args: Any,
        max_size: int = 128,
        cache: Optional[OrderedDict[Path, Cache]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        self._cache: OrderedDict[Path, Cache] = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        if cache is not None:
            self._cache.update(cache)

    def cache_hit(self, hashed_context: str, cache_type: CacheType) -> bool:
        key = self.build_path(hashed_context, cache_type)
        return key in self._cache

    def load_cache(self, hashed_context: str, cache_type: CacheType) -> Cache:
        assert self.cache_hit(
            hashed_context, cache_type
        ), INCONSISTENT_CACHE_BOILER_PLATE
        self.hits += 1
        key = self.build_path(hashed_context, cache_type)
        if self.max_size > 0:
            self._cache.move_to_end(key)
        return self._cache[key]

    def save_cache(self, cache: Cache) -> None:
        key = self.build_path(cache.hash, cache.cache_type)
        self._cache[key] = cache
        # LRU
        if self.max_size > 0:
            self._cache.move_to_end(key)
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def resize(self, max_size: int) -> None:
        if max_size <= 0:
            self.max_size = max_size
            return
        while len(self._cache) > max_size:
            self._cache.popitem(last=False)
        self.max_size = max_size
