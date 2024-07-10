# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._save.cache import CACHE_PREFIX, Cache, CacheType

if TYPE_CHECKING:
    from marimo._ast.visitor import Name

INCONSISTENT_CACHE_BOILER_PLATE = (
    "The cache state does not match "
    "expectations, this can be due to file "
    "corruption or an incompatible marimo "
    "version. Alternatively, this may be a bug"
    " in marimo. Please file an issue at "
    "github.com/marimo-team/marimo/issues"
)


class Loader(ABC):
    """Loaders are responsible for saving and loading persistent caches.

    Loaders are provided a name, a save path and a cache key or "hash", which
    should be deterministically determined given the notebook context.

    In the future, they may be specialized for different types of data (such as
    numpy or pandas dataframes), or remote storage (such as S3 or marimo
    cloud).
    """

    def __init__(self, name: str, save_path: str) -> None:
        self.name = name
        self.save_path = Path(save_path) / name
        self.save_path.mkdir(parents=True, exist_ok=True)

    def build_path(self, hashed_context: str, cache_type: CacheType) -> Path:
        prefix = CACHE_PREFIX.get(cache_type, "U_")
        return self.save_path / f"{prefix}{hashed_context}"

    def cache_attempt(
        self, defs: set[Name], hashed_context: str, cache_type: CacheType
    ) -> Cache:
        if not self.cache_hit(hashed_context, cache_type):
            return Cache(
                {d: None for d in defs}, hashed_context, cache_type, False
            )
        loaded = self.load_cache(hashed_context, cache_type)
        # TODO: Consider more robust verification
        assert loaded.hash == hashed_context, INCONSISTENT_CACHE_BOILER_PLATE
        assert set(defs) == set(loaded.defs), INCONSISTENT_CACHE_BOILER_PLATE
        return Cache(loaded.defs, hashed_context, cache_type, True)

    @abstractmethod
    def cache_hit(self, hashed_context: str, cache_type: CacheType) -> bool:
        """Check if cache has been hit given a result hash.

        Args:
            hashed_context: The hash of the result context
            cache_type: The type of cache to check for

        Returns:
            bool: Whether the cache has been hit
        """

    @abstractmethod
    def load_cache(self, hashed_context: str, cache_type: CacheType) -> Cache:
        """Load Cache"""

    @abstractmethod
    def save_cache(self, cache: Cache) -> None:
        """Save Cache"""


class PickleLoader(Loader):
    """General loader for serializable objects."""

    def build_path(self, hashed_context: str, cache_type: CacheType) -> Path:
        return Path(f"{super().build_path(hashed_context, cache_type)}.pickle")

    def cache_hit(self, hashed_context: str, cache_type: CacheType) -> bool:
        return os.path.exists(self.build_path(hashed_context, cache_type))

    def load_cache(self, hashed_context: str, cache_type: CacheType) -> Cache:
        assert self.cache_hit(
            hashed_context, cache_type
        ), INCONSISTENT_CACHE_BOILER_PLATE
        with open(self.build_path(hashed_context, cache_type), "rb") as handle:
            cache = pickle.load(handle)
            assert isinstance(cache, Cache), (
                "Excepted cache object, got" f"{type(cache)} ",
                INCONSISTENT_CACHE_BOILER_PLATE,
            )
            return cache

    def save_cache(self, cache: Cache) -> None:
        with open(self.build_path(cache.hash, cache.cache_type), "wb") as f:
            pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
