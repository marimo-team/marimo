# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar, Union

from marimo._save.cache import Cache
from marimo._save.loaders.loader import Loader

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._save.hash import HashKey


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
        self._max_size = max_size
        if cache is not None:
            self._maybe_lock(lambda: self._cache.update(cache))

    def _maybe_lock(self, fn: Callable[..., T]) -> T:
        if self._cache_lock is not None:
            with self._cache_lock:
                return fn()
        else:
            return fn()

    def cache_hit(self, key: HashKey) -> bool:
        path = self.build_path(key)
        return self._maybe_lock(lambda: path in self._cache)

    def load_cache(self, key: HashKey) -> Optional[Cache]:
        if not self.cache_hit(key):
            return None
        path = self.build_path(key)
        if self.is_lru:
            assert isinstance(self._cache, OrderedDict)
            assert self._cache_lock is not None
            with self._cache_lock:
                self._cache.move_to_end(path)
        return self._cache[path]

    def save_cache(self, cache: Cache) -> bool:
        path = self.build_path(cache.key)
        # LRU
        if self.is_lru:
            assert isinstance(self._cache, OrderedDict)
            assert self._cache_lock is not None
            with self._cache_lock:
                self._cache[path] = cache
                self._cache.move_to_end(path)
                if len(self._cache) > self.max_size:
                    self._cache.popitem(last=False)
        self._cache[path] = cache
        return True

    def resize(self, max_size: int) -> None:
        if not self.is_lru:
            self.is_lru = max_size > 0
            if self.is_lru:
                self._cache = OrderedDict(self._cache.items())
                self._cache_lock = threading.Lock()
            self._max_size = max_size
            return
        assert isinstance(self._cache, OrderedDict)
        assert self._cache_lock is not None
        with self._cache_lock:
            self.is_lru = max_size > 0
            if not self.is_lru:
                self._cache = dict(self._cache.items())
                self._max_size = max_size
                return
            while len(self._cache) > max_size:
                self._cache.popitem(last=False)
        self._max_size = max_size

    @property
    def max_size(self) -> int:
        return self._max_size

    @max_size.setter
    def max_size(self, value: int) -> None:
        self.resize(value)
