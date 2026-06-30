# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._save.stores.store import Store


class DictStore(Store):
    """A minimal dict-backed store for in-session caching."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self._data.get(key)

    def put(self, key: str, value: bytes) -> bool:
        self._data[key] = value
        return True

    def hit(self, key: str) -> bool:
        return key in self._data

    def clear(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            return True
        return False
