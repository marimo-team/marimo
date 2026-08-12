# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
from typing import cast

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


def get_store(current_path: str | None = None) -> Store:
    from marimo._config.manager import get_default_config_manager

    config = get_default_config_manager(current_path=current_path).get_config()
    # Top-level [cache].store supersedes the legacy experimental.cache location.
    store_config: CacheStoreConfig | None = config.get("cache", {}).get(
        "store"
    )
    if store_config is None:
        store_config = config.get("experimental", {}).get("cache", None)

    return _get_store_from_config(store_config)


def cache_store_is_untrusted(current_path: str | None = None) -> bool:
    """Whether `cache.store` was set by an untrusted (project/script) layer.

    The user layer is trusted and the env layer never sets a store, so a store
    config present in the merged *overrides* (project pyproject.toml or notebook
    header) is untrusted origin. Used to stop the unsigned pickle loader from
    being redirected at an attacker-chosen store.
    """
    from marimo._config.manager import get_default_config_manager

    overrides = get_default_config_manager(
        current_path=current_path
    ).get_config_overrides()
    store = overrides.get("cache", {}).get("store")
    if store is None:
        store = overrides.get("experimental", {}).get("cache")
    return store is not None


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
        # `type` is the documented key. The legacy `experimental.cache` reader
        # spelled it `store`, so accept that too rather than silently falling
        # back to the default store — a silent cache miss is the worst outcome
        # here, since the cache still "works" while never hitting.
        store_type = cast(StoreKey, config.get("type") or DEFAULT_STORE_KEY)
        if "type" not in config and "store" in config:
            store_type = cast(StoreKey, config["store"])  # type: ignore[typeddict-item]
            LOGGER.warning(
                "Cache store config uses the legacy key `store = %r`; rename "
                "it to `type = %r`.",
                store_type,
                store_type,
            )
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
