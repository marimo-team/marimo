from __future__ import annotations

from typing import Any, Dict, Optional

from marimo._save.cache import Cache, CacheType
from marimo._save.loaders import Loader


class MockLoader(Loader):
    def __init__(
        self,
        name: str = "mock",
        save_path: str = "",
        data: Optional[Dict[str, Any]] = None,
        stateful_refs: Optional[set[str]] = None,
    ) -> None:
        self.name = name
        self.save_path = save_path
        self._data = data or {}
        self._cache_hit = data is not None
        self._loaded = False
        self._saved = False
        self._stateful_refs = stateful_refs or set()

    def cache_hit(self, _hashed_context: str, _cache_type: CacheType) -> bool:
        return self._cache_hit

    def load_cache(self, hashed_context: str, cache_type: CacheType) -> Cache:
        self._loaded = True
        return Cache(
            self._data,
            hashed_context,
            self._stateful_refs,
            cache_type,
            True,
            {},
        )

    def save_cache(self, _cache: Cache) -> None:
        self._saved = True
