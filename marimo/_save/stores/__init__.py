# Copyright 2025 Marimo. All rights reserved.
from typing import Literal

from marimo._save.stores.file import FileStore
from marimo._save.stores.redis import RedisStore
from marimo._save.stores.store import Store, StoreType

StoreKey = Literal["file", "redis"]

CACHE_STORES: dict[StoreKey, StoreType] = {
    "file": FileStore,
    "redis": RedisStore,
}
DEFAULT_STORE_KEY: StoreKey = "file"
DEFAULT_STORE: StoreType = CACHE_STORES[DEFAULT_STORE_KEY]


def get_store() -> Store:
    from marimo._config.manager import get_default_config_manager

    cache_config = (
        get_default_config_manager(current_path=None)
        .get_config()
        .get("experimental", {})
        .get("cache", {})
    )
    store_type = cache_config.get("store", DEFAULT_STORE_KEY)
    assert store_type in CACHE_STORES, f"Invalid store type: {store_type}"
    return CACHE_STORES[store_type](**cache_config.get("args", {}))


__all__ = [
    "CACHE_STORES",
    "DEFAULT_STORE",
    "FileStore",
    "RedisStore",
    "Store",
    "StoreKey",
    "StoreType",
    "get_store",
]
