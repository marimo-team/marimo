# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import json

from marimo._save.cache import Cache, CacheType
from marimo._save.loaders.loader import BasePersistenceLoader, LoaderError


class JsonLoader(BasePersistenceLoader):
    """Readable json loader for basic objects."""

    def __init__(self, name: str, save_path: str) -> None:
        super().__init__(name, "json", save_path)

    def load_persistent_cache(
        self, hashed_context: str, cache_type: CacheType
    ) -> Cache:
        with open(self.build_path(hashed_context, cache_type), "rb") as handle:
            cache = json.load(handle)
            # Handle unserializable stateful_refs
            cache["stateful_refs"] = set(cache["stateful_refs"])
            try:
                return Cache(**cache)
            except TypeError as e:
                raise LoaderError(
                    "Invalid json object for cache restoration"
                ) from e

    def save_cache(self, cache: Cache) -> None:
        with open(self.build_path(cache.hash, cache.cache_type), "w") as f:
            dump = dataclasses.asdict(cache)
            dump["stateful_refs"] = list(dump["stateful_refs"])
            json.dump(dump, f, indent=4)
