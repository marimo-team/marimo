# Copyright 2025 Marimo. All rights reserved.
from typing import Literal, Optional

from marimo import _loggers
from marimo._save.stores.file import FileStore
from marimo._save.stores.redis import RedisStore
from marimo._save.stores.rest import RestStore
from marimo._save.stores.store import Store, StoreType

LOGGER = _loggers.marimo_logger()

StoreKey = Literal["file", "redis", "rest"]

CACHE_STORES: dict[StoreKey, StoreType] = {
    "file": FileStore,
    "redis": RedisStore,
    "rest": RestStore,
}
DEFAULT_STORE_KEY: StoreKey = "file"
DEFAULT_STORE: StoreType = CACHE_STORES[DEFAULT_STORE_KEY]


def get_store(current_path: Optional[str] = None) -> Store:
    from marimo._config.manager import get_default_config_manager

    cache_config = (
        get_default_config_manager(current_path=current_path)
        .get_config()
        .get("experimental", {})
        .get("cache", {})
    )
    store_type = cache_config.get("store", DEFAULT_STORE_KEY)
    if store_type not in CACHE_STORES:
        LOGGER.error(f"Invalid store type: {store_type}")
        store_type = DEFAULT_STORE_KEY
    try:
        return CACHE_STORES[store_type](**cache_config.get("args", {}))
    except Exception as e:
        LOGGER.error(f"Error creating store: {e}")
        return DEFAULT_STORE()


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
