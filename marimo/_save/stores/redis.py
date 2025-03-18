# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._save.cache import (
    Cache,
)
from marimo._save.stores.store import Store

if TYPE_CHECKING:
    from marimo._save.hash import HashKey
    from marimo._save.loaders import BasePersistenceLoader as Loader


class RedisStore(Store):
    def __init__(self) -> None:
        import redis

        self.redis = redis.Redis()

    def get(self, key: HashKey, loader: Loader) -> bytes:
        return self.redis.get(str(loader.build_path(key))) or b""

    def put(self, cache: Cache, loader: Loader) -> None:
        self.redis.set(
            str(loader.build_path(cache.key)), loader.to_blob(cache) or b""
        )

    def hit(self, key: HashKey, loader: Loader) -> bool:
        return self.redis.exists(str(loader.build_path(key))) > 0
