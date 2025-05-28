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
        config_value: Any = None,
        strict: bool = False,
    ) -> None:
        self.save_path = save_path
        self._data = data or {}
        self._cache_hit = data is not None
        self._loaded = False
        self._saved = False
        self._stateful_refs = stateful_refs or set()
        self.config_value = config_value
        # "Strict" is more than just spoofing the response, but actually going
        # through the hydration process.
        self.strict = strict
        super().__init__(name)

    def cache_hit(self, _) -> bool:
        return self._cache_hit

    def load_cache(self, key) -> Optional[Cache]:
        if not self._cache_hit:
            return None
        self._loaded = True
        data = self._data
        if self.strict:
            data = {key: None for key in self._data}
        cache = Cache(
            defs=data,
            hash=key.hash,
            cache_type=key.cache_type,
            stateful_refs=self._stateful_refs,
            hit=True,
            meta={},
        )
        if self.strict:
            cache.update(self._data)
        return cache

    def save_cache(self, _cache: Cache) -> bool:
        self._saved = True
        self._cache_hit = True
        return True
