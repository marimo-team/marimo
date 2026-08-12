# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._save.cache import Cache
from marimo._save.loaders.loader import BasePersistenceLoader, LoaderError

if TYPE_CHECKING:
    from marimo._save.hash import HashKey

LOGGER = _loggers.marimo_logger()


class PickleLoader(BasePersistenceLoader):
    """General loader for serializable objects."""

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, "pickle", **kwargs)
        # NB. `restore_cache` pickle.loads with no verification, so an
        # untrusted layer's store must not reach it. An explicit store is
        # trusted caller code — only the session-configured store is guarded.
        if kwargs.get("store") is None and self._store_is_untrusted_origin():
            from marimo._save.stores import DEFAULT_STORE

            self.store = DEFAULT_STORE()
            LOGGER.warning(
                "Ignoring cache.store from an untrusted config layer for the "
                "unsigned pickle loader (it would feed pickle.loads); using the "
                "default store. Use method='lazy' to verify a shared store, or "
                "configure the store in user config."
            )

    @staticmethod
    def _store_is_untrusted_origin() -> bool:
        from marimo._runtime.context import get_context
        from marimo._runtime.context.types import (
            ContextNotInitializedError,
        )

        try:
            return get_context().cache.store_from_untrusted_origin
        except ContextNotInitializedError:
            return False

    def restore_cache(self, key: HashKey, blob: bytes) -> Cache:
        del key
        cache = pickle.loads(blob)
        if not isinstance(cache, Cache):
            raise LoaderError(f"Excepted cache object, got{type(cache)}")
        return cache

    def to_blob(self, cache: Cache) -> bytes:
        return pickle.dumps(cache, protocol=pickle.HIGHEST_PROTOCOL)
