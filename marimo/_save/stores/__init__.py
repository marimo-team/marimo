# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
from typing import Any, cast

from marimo import _loggers
from marimo._config.config import CacheStoreConfig, StoreKey
from marimo._entrypoints.registry import EntryPointRegistry
from marimo._save.stores.file import FileStore
from marimo._save.stores.redis import RedisStore
from marimo._save.stores.rest import RestStore
from marimo._save.stores.store import Store, StoreType
from marimo._save.stores.tiered import TieredStore

LOGGER = _loggers.marimo_logger()


CACHE_STORES: dict[StoreKey, StoreType] = {
    "file": FileStore,
    "redis": RedisStore,
    "rest": RestStore,
    "tiered": TieredStore,
}
DEFAULT_STORE_KEY: StoreKey = "file"
DEFAULT_STORE: StoreType = CACHE_STORES[DEFAULT_STORE_KEY]

_STORE_REGISTRY = EntryPointRegistry[StoreType](
    "marimo.cache.store",
)


def _store_config(config: Any) -> CacheStoreConfig | None:
    """Read the store config out of a (possibly partial) marimo config.

    Shared by `get_store` and `cache_store_is_untrusted` so store selection and
    the provenance check can never disagree about which key they read.
    """
    return cast(
        "CacheStoreConfig | None", config.get("cache", {}).get("store")
    )


def get_store(current_path: str | None = None) -> Store:
    from marimo._config.manager import get_default_config_manager

    config = get_default_config_manager(current_path=current_path).get_config()
    return _get_store_from_config(_store_config(config))


def cache_store_is_untrusted(current_path: str | None = None) -> bool:
    """Whether `cache.store` came from a layer that travels with the code."""
    # NB. only the overrides are inspected, because a store can reach the user
    # layer solely through a workspace `.marimo.toml`, and that layer has its
    # store stripped during config load for exactly this reason.
    from marimo._config.manager import get_default_config_manager

    overrides = get_default_config_manager(
        current_path=current_path
    ).get_config_overrides()
    return _store_config(overrides) is not None


def _get_store_from_config(
    config: CacheStoreConfig | None,
    registry: EntryPointRegistry[StoreType] = _STORE_REGISTRY,
) -> Store:
    if config is None:
        return DEFAULT_STORE()

    cache_stores = copy.copy(cast(dict[str, StoreType], CACHE_STORES))
    cache_stores.update(
        {name: registry.get(name) for name in registry.names()}
    )

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
        store_type = cast(StoreKey, config.get("type", DEFAULT_STORE_KEY))
        if store_type not in cache_stores:
            LOGGER.error(f"Invalid store type: {store_type}")
            store_type = DEFAULT_STORE_KEY

        try:
            store_args = config.get("args", {})
            return cache_stores[store_type](**store_args)
        except Exception as e:
            LOGGER.error(f"Error creating store: {e}")
            return DEFAULT_STORE()


__all__ = [
    "CACHE_STORES",
    "DEFAULT_STORE",
    "FileStore",
    "RedisStore",
    "RestStore",
    "Store",
    "StoreKey",
    "StoreType",
    "TieredStore",
    "get_store",
]
