# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from marimo._save.cache import (
    Cache,
)

if TYPE_CHECKING:
    from marimo._save.hash import HashKey
    from marimo._save.loaders import BasePersistenceLoader as Loader


class Store(ABC):
    _instance = None

    # Singleton
    def __new__(cls) -> Store:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Put any initialization here.
        return cls._instance

    @abstractmethod
    def get(self, key: HashKey, loader: Loader) -> Optional[bytes]:
        """Get the bytes of a cache from the store"""

    @abstractmethod
    def put(self, cache: Cache, loader: Loader) -> None:
        """Put a cache into the store"""

    @abstractmethod
    def hit(self, key: HashKey, loader: Loader) -> bool:
        """Check if the cache is in the store"""


StoreType = type[Store]
