# Copyright 2025 Marimo. All rights reserved.
from typing import Any, Literal, Optional, TypedDict, Union, cast

from marimo import _loggers
from marimo._save.stores.file import FileStore
from marimo._save.stores.redis import RedisStore
from marimo._save.stores.rest import RestStore
from marimo._save.stores.store import Store, StoreType
from marimo._save.stores.tiered import TieredStore

LOGGER = _loggers.marimo_logger()

StoreKey = Literal["file", "redis", "rest", "tiered"]


class StoreConfig(TypedDict, total=False):
    type: StoreKey
    args: dict[str, Any]


CACHE_STORES: dict[StoreKey, StoreType] = {
    "file": FileStore,
    "redis": RedisStore,
    "rest": RestStore,
    "tiered": TieredStore,
}
DEFAULT_STORE_KEY: StoreKey = "file"
DEFAULT_STORE: StoreType = CACHE_STORES[DEFAULT_STORE_KEY]


def get_store(current_path: Optional[str] = None) -> Store:
    from marimo._config.manager import get_default_config_manager

    cache_config: Union[list[StoreConfig], StoreConfig] = (
        get_default_config_manager(current_path=current_path)
        .get_config()
        .get("experimental", {})
        .get("cache", {})
    )

    return _get_store_from_config(cache_config)


def _get_store_from_config(
    config: Union[list[StoreConfig], StoreConfig, None],
) -> Store:
    if config is None:
        return DEFAULT_STORE()

    if isinstance(config, list):
        sub_stores = [
            _get_store_from_config(item) for item in config if item is not None
        ]
        if len(sub_stores) == 0:
            return DEFAULT_STORE()
        if len(sub_stores) == 1:
            return sub_stores[0]
        return TieredStore(sub_stores)
    else:
        store_type = cast(StoreKey, config.get("store", DEFAULT_STORE_KEY))
        if store_type not in CACHE_STORES:
            LOGGER.error(f"Invalid store type: {store_type}")
            store_type = DEFAULT_STORE_KEY

        try:
            store_args = config.get("args", {})
            return CACHE_STORES[store_type](**store_args)
        except Exception as e:
            LOGGER.error(f"Error creating store: {e}")
            return DEFAULT_STORE()


__all__ = [
    "CACHE_STORES",
    "DEFAULT_STORE",
    "FileStore",
    "RedisStore",
    "RestStore",
    "TieredStore",
    "Store",
    "StoreKey",
    "StoreType",
    "get_store",
]
