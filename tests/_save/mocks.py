from __future__ import annotations

from typing import Any, Optional

from marimo._save.cache import Cache
from marimo._save.loaders import Loader


class MockLoader(Loader):
    def __init__(
        self,
        name: str = "mock",
        save_path: str = "",
        data: Optional[dict[str, Any]] = None,
        stateful_refs: Optional[set[str]] = None,
    ) -> None:
        self.save_path = save_path
        self._data = data or {}
        self._cache_hit = data is not None
        self._loaded = False
        self._saved = False
        self._stateful_refs = stateful_refs or set()
        super().__init__(name)

    def cache_hit(self, _) -> bool:
        return self._cache_hit

    def load_cache(self, key) -> Cache:
        self._loaded = True
        return Cache(
            self._data,
            key,
            self._stateful_refs,
            True,
            {},
        )

    def save_cache(self, _cache: Cache) -> None:
        self._saved = True
