from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from marimo._save.stores import Store

if TYPE_CHECKING:
    from marimo._save.cache import Cache
    from marimo._save.hash import HashKey
    from marimo._save.loaders import Loader


class MockStore(Store):
    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[str, Any] = {}

    def get(self, key: HashKey, _loader: Loader) -> Optional[bytes]:
        return self._cache.get(key.hash, None)

    def put(self, cache: Cache, _loader: Loader) -> None:
        self._cache[cache.key.hash] = cache

    def hit(self, key: HashKey, _loader: Loader) -> bool:
        return key in self._cache
