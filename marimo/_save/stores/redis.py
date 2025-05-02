# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional

from marimo._save.stores.store import Store


class RedisStore(Store):
    def __init__(self, **kwargs: Any) -> None:
        import redis

        # TODO: Construct from a full config dataclass, and pass in kwargs
        # opposed to experimental.store.redis.args
        # See list of options here:
        self.redis = redis.Redis(**kwargs)

    def get(self, key: str) -> Optional[bytes]:
        result = self.redis.get(key)
        if result is None:
            return None
        return result.encode("utf-8")  # type: ignore[no-any-return]

    def put(self, key: str, value: bytes) -> None:
        self.redis.set(key, value)

    def hit(self, key: str) -> bool:
        return self.redis.exists(key) > 0
