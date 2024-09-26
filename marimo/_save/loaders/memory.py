# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar, Union

from marimo._save.cache import Cache, CacheType
from marimo._save.loaders.loader import INCONSISTENT_CACHE_BOILER_PLATE, Loader

if TYPE_CHECKING:
    from pathlib import Path


T = TypeVar("T")


class MemoryLoader(Loader):
    """In memory loader for saved objects."""

    def __init__(
        self,
        *args: Any,
        max_size: int = 128,
        cache: Optional[OrderedDict[Path, Cache]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        self._cache: Union[OrderedDict[Path, Cache], dict[Path, Cache]]
        self.is_lru = max_size > 0

        # Normal python dicts are atomic, ordered dictionaries are not.
        # As such, default to normal dict if not LRU.
        self._cache = {}
        # ordered dict is protected by a lock
        self._cache_lock: threading.Lock | None = None
        if self.is_lru:
            self._cache = OrderedDict()
            self._cache_lock = threading.Lock()
        self.max_size = max_size
        self.hits = 0
        if cache is not None:
            self._maybe_lock(lambda: self._cache.update(cache))

    def _maybe_lock(self, fn: Callable[..., T]) -> T:
        if self._cache_lock is not None:
            with self._cache_lock:
                return fn()
        else:
            return fn()

    def cache_hit(self, hashed_context: str, cache_type: CacheType) -> bool:
        key = self.build_path(hashed_context, cache_type)
        return self._maybe_lock(lambda: key in self._cache)

    def load_cache(self, hashed_context: str, cache_type: CacheType) -> Cache:
        assert self.cache_hit(
            hashed_context, cache_type
        ), INCONSISTENT_CACHE_BOILER_PLATE
        self.hits += 1
        key = self.build_path(hashed_context, cache_type)
        if self.is_lru:
            assert isinstance(self._cache, OrderedDict)
            assert self._cache_lock is not None
            with self._cache_lock:
                self._cache.move_to_end(key)
        return self._cache[key]

    def save_cache(self, cache: Cache) -> None:
        key = self.build_path(cache.hash, cache.cache_type)
        # LRU
        if self.is_lru:
            assert isinstance(self._cache, OrderedDict)
            assert self._cache_lock is not None
            with self._cache_lock:
                self._cache[key] = cache
                self._cache.move_to_end(key)
                if len(self._cache) > self.max_size:
                    self._cache.popitem(last=False)
        self._cache[key] = cache

    def resize(self, max_size: int) -> None:
        if not self.is_lru:
            self.is_lru = max_size > 0
            if self.is_lru:
                self._cache = OrderedDict(self._cache.items())
                self._cache_lock = threading.Lock()
            self.max_size = max_size
            return
        assert isinstance(self._cache, OrderedDict)
        assert self._cache_lock is not None
        with self._cache_lock:
            self.is_lru = max_size > 0
            if not self.is_lru:
                self._cache = dict(self._cache.items())
                self.max_size = max_size
                return
            while len(self._cache) > max_size:
                self._cache.popitem(last=False)
        self.max_size = max_size
