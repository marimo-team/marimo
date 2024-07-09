# Copyright 2024 Marimo. All rights reserved.

import os
import pickle
from abc import ABC, abstractmethod
from pathlib import Path

from marimo._save.cache import CACHE_PREFIX


class Loader(ABC):
    """Loaders are responsible for saving and loading persistent caches.

    Loaders are provided a name, a save path and a cache key or "hash", which
    should be deterministically determined given the notebook context.

    In the future, they may be specialized for different types of data (such as
    numpy or pandas dataframes), or remote storage (such as S3 or marimo cloud)."""

    def __init__(self, name, save_path):
        self.name = name
        self.save_path = Path(save_path) / name
        self.save_path.mkdir(parents=True, exist_ok=True)

    def build_path(self, hashed_context, cache_type):
        prefix = CACHE_PREFIX.get(cache_type, "U_")
        return self.save_path / f"{prefix}{hashed_context}"

    def cache_attempt(self, defs, hashed_context, cache_type):
        if not self.cache_hit(hashed_context, cache_type):
            return Cache(
                {d: None for d in defs}, hashed_context, cache_type, False
            )
        loaded = self.load_cache(hashed_context, cache_type)
        # TODO: Consider more robust verification
        assert loaded.hash == hashed_context
        assert set(defs) == set(loaded.defs)
        return Cache(loaded.defs, hashed_context, cache_type, True)

    @abstractmethod
    def cache_hit(self, hashed_context, cache_type):
        """Check if cache has been hit given a result hash.

        Args:
            hashed_context: The hash of the result context
            cache_type: The type of cache to check for

        Returns:
            bool: Whether the cache has been hit
        """

    @abstractmethod
    def load_cache(self, hashed_context, cache_type):
        """Load Cache gi"""

    @abstractmethod
    def save_cache(self, cache):
        """Save Cache"""


class PickleLoader(Loader):
    """General loader for serialable objects."""

    def build_path(self, hashed_context, cache_type):
        return f"{super().build_path(hashed_context, cache_type)}.pickle"

    def cache_hit(self, hashed_context, cache_type):
        return os.path.exists(self.build_path(hashed_context, cache_type))

    def load_cache(self, hashed_context, cache_type):
        assert self.cache_hit(hashed_context, cache_type)
        with open(self.build_path(hashed_context, cache_type), "rb") as handle:
            return pickle.load(handle)

    def save_cache(self, cache):
        with open(self.build_path(cache.hash, cache.cache_type), "wb") as f:
            pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
