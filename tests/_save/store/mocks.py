from __future__ import annotations

from typing import Any, Optional

from marimo._save.stores import Store


class MockStore(Store):
    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[str, Any] = {}

    def get(self, key: str) -> Optional[bytes]:
        return self._cache.get(key, None)

    def put(self, key: str, value: bytes) -> bool:
        self._cache[key] = value
        return True

    def hit(self, key: str) -> bool:
        return key in self._cache
