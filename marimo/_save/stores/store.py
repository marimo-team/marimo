# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class Store(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """Get the bytes of a cache from the store"""

    @abstractmethod
    def put(self, key: str, value: bytes) -> bool:
        """Put a cache into the store"""

    @abstractmethod
    def hit(self, key: str) -> bool:
        """Check if the cache is in the store"""

    def clear(self, key: str) -> bool:
        """Check if the cache is in the store"""
        del key
        return False

    def flush(self) -> None:  # noqa: B027
        """Wait for any pending async writes to complete.

        No-op by default. Stores with async writes should override.
        """


StoreType = type[Store]
