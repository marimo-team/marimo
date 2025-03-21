# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from marimo._save.cache import (
    Cache,
)
from marimo._save.stores.store import Store

if TYPE_CHECKING:
    from marimo._save.hash import HashKey
    from marimo._save.loaders import BasePersistenceLoader as Loader


class RedisStore(Store):
    def __init__(self, **kwargs: Any) -> None:
        import redis

        # TODO: Construct from a full config dataclass, and pass in kwargs
        # opposed to experimental.store.redis.args
        # See list of options here:
        self.redis = redis.Redis(**kwargs)

    def get(self, key: HashKey, loader: Loader) -> Optional[bytes]:
        return self.redis.get(str(loader.build_path(key))) or None

    def put(self, cache: Cache, loader: Loader) -> None:
        self.redis.set(
            str(loader.build_path(cache.key)), loader.to_blob(cache) or b""
        )

    def hit(self, key: HashKey, loader: Loader) -> bool:
        return self.redis.exists(str(loader.build_path(key))) > 0
