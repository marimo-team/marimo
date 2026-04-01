# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional

from marimo._save.stores.store import Store


class RedisStore(Store):
    """A cache store backed by a Redis instance."""

    def __init__(self, **kwargs: Any) -> None:
        import redis

        # TODO: Construct from a full config dataclass, and pass in kwargs
        # opposed to experimental.store.redis.args
        # See list of options here:
        self.redis = redis.Redis(**kwargs)

    def get(self, key: str) -> Optional[bytes]:
        """Retrieve the cached bytes for the given key from Redis, or None if missing."""
        result = self.redis.get(key)
        if result is None:
            return None
        return result  # type: ignore[no-any-return]

    def put(self, key: str, value: bytes) -> bool:
        """Store bytes under the given key in Redis, returning True on success."""
        result = self.redis.set(key, value)
        if result is None:
            return False
        return True

    def hit(self, key: str) -> bool:
        """Return True if the given key exists in Redis."""
        return self.redis.exists(key) > 0
