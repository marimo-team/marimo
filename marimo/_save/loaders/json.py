# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import json

from marimo._save.cache import Cache
from marimo._save.hash import HashKey
from marimo._save.loaders.loader import BasePersistenceLoader, LoaderError


class JsonLoader(BasePersistenceLoader):
    """Readable json loader for basic objects."""

    def __init__(self, name: str, save_path: str) -> None:
        super().__init__(name, "json", save_path)

    def restore_cache(self, key: HashKey, blob: bytes) -> Cache:
        del key
        cache = json.loads(blob)
        # Handle unserializable stateful_refs
        cache["stateful_refs"] = set(cache["stateful_refs"])
        try:
            hash_key = cache.pop("key", {})
            return Cache(**hash_key, **cache)
        except TypeError as e:
            raise LoaderError(
                "Invalid json object for cache restoration"
            ) from e

    def to_blob(self, cache: Cache) -> bytes:
        dump = dataclasses.asdict(cache)
        dump["stateful_refs"] = list(dump["stateful_refs"])
        return json.dumps(dump, indent=4).encode("utf-8")
