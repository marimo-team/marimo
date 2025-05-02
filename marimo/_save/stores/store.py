# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Store(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """Get the bytes of a cache from the store"""

    @abstractmethod
    def put(self, key: str, value: bytes) -> None:
        """Put a cache into the store"""

    @abstractmethod
    def hit(self, key: str) -> bool:
        """Check if the cache is in the store"""


StoreType = type[Store]
