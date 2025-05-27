# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo import _loggers
from marimo._save.stores.store import Store

LOGGER = _loggers.marimo_logger()


class TieredStore(Store):
    """A composite store that tries multiple stores in order.

    Reads will check each store in order until the data is found.
    Writes will update all stores.
    """

    def __init__(self, stores: list[Store]) -> None:
        """Initialize the tiered store with a list of stores.

        Args:
            stores: List of stores to use, in order of priority
        """
        if not stores:
            raise ValueError("At least one store is required")
        self.stores = stores

    def get(self, key: str) -> Optional[bytes]:
        """Get a value from the first store that has it."""
        for i, store in enumerate(self.stores):
            try:
                value = store.get(key)
                if value is not None:
                    # Found in this store, update preceding stores
                    self._update_preceding_stores(key, value, i)
                    return value
            except Exception as e:
                LOGGER.error(f"Error getting from store {i}: {e}")

        return None

    def put(self, key: str, value: bytes) -> bool:
        """Put a value in all stores."""
        success = False

        for i, store in enumerate(self.stores):
            try:
                if store.put(key, value):
                    success = True
            except Exception as e:
                LOGGER.error(f"Error putting to store {i}: {e}")

        return success

    def hit(self, key: str) -> bool:
        """Check if any store has the key."""
        for i, store in enumerate(self.stores):
            try:
                if store.hit(key):
                    return True
            except Exception as e:
                LOGGER.error(f"Error checking hit on store {i}: {e}")

        return False

    def _update_preceding_stores(
        self, key: str, value: bytes, found_index: int
    ) -> None:
        """Update all stores before the one where the value was found."""
        for i in range(found_index):
            try:
                self.stores[i].put(key, value)
            except Exception as e:
                LOGGER.error(f"Error updating preceding store {i}: {e}")
