# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from marimo._save.stores.tiered import TieredStore
from tests._save.store.mocks import MockStore


def throw_exception(*args: Any, **kwargs: Any) -> None:
    del args, kwargs
    raise ValueError("Test exception")


class TestTieredStore:
    def test_init_with_empty_stores_raises_error(self) -> None:
        """Test that initializing with empty stores raises an error."""
        with pytest.raises(ValueError, match="At least one store is required"):
            TieredStore([])

    def test_init_with_multiple_stores(self) -> None:
        """Test that initializing with multiple stores works."""
        stores = [MockStore(), MockStore()]
        tiered_store = TieredStore(stores)
        assert tiered_store.stores == stores

    def test_get_from_first_store(self) -> None:
        """Test getting a value that exists in the first store."""
        store1 = MockStore()
        store2 = MockStore()
        key = "test_key"
        value = b"test_value"
        store1._cache[key] = value

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.get(key)

        assert result == value
        # Second store should remain empty
        assert key not in store2._cache

    def test_get_from_second_store_updates_first(self) -> None:
        """Test getting a value from the second store updates the first store."""
        store1 = MockStore()
        store2 = MockStore()
        key = "test_key"
        value = b"test_value"
        store2._cache[key] = value

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.get(key)

        assert result == value
        # First store should be updated
        assert key in store1._cache
        assert store1._cache[key] == value

    def test_get_not_found(self) -> None:
        """Test that get returns None when the key is not found in any store."""
        store1 = MockStore()
        store2 = MockStore()
        key = "test_key"

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.get(key)

        assert result is None

    def test_put_updates_all_stores(self) -> None:
        """Test that put updates all stores."""
        store1 = MockStore()
        store2 = MockStore()
        key = "test_key"
        value = b"test_value"

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.put(key, value)

        assert result is True
        assert key in store1._cache
        assert store1._cache[key] == value
        assert key in store2._cache
        assert store2._cache[key] == value

    def test_hit_returns_true_if_any_store_has_key(self) -> None:
        """Test that hit returns True if any store has the key."""
        store1 = MockStore()
        store2 = MockStore()
        key = "test_key"
        value = b"test_value"
        store2._cache[key] = value

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.hit(key)

        assert result is True

    def test_hit_returns_false_if_no_store_has_key(self) -> None:
        """Test that hit returns False if no store has the key."""
        store1 = MockStore()
        store2 = MockStore()
        key = "test_key"

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.hit(key)

        assert result is False

    @patch("marimo._save.stores.tiered.LOGGER")
    def test_get_with_exception(self, mock_logger) -> None:
        """Test handling exceptions during get operation."""
        store1 = MockStore()
        # Create a store that will raise an exception
        store2 = MockStore()
        store2.get = throw_exception

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.get("test_key")

        assert result is None
        mock_logger.error.assert_called_once()
        assert "Test exception" in mock_logger.error.call_args[0][0]

    @patch("marimo._save.stores.tiered.LOGGER")
    def test_put_with_exception(self, mock_logger) -> None:
        """Test handling exceptions during put operation."""
        store1 = MockStore()
        # Create a store that will raise an exception
        store2 = MockStore()
        store2.put = throw_exception

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.put("test_key", b"test_value")

        # Should still return True because store1 succeeded
        assert result is True
        mock_logger.error.assert_called_once()
        assert "Test exception" in mock_logger.error.call_args[0][0]

    @patch("marimo._save.stores.tiered.LOGGER")
    def test_hit_with_exception(self, mock_logger) -> None:
        """Test handling exceptions during hit operation."""
        store1 = MockStore()
        # Create a store that will raise an exception
        store2 = MockStore()
        store2.hit = throw_exception

        tiered_store = TieredStore([store1, store2])
        result = tiered_store.hit("test_key")

        assert result is False
        mock_logger.error.assert_called_once()
        assert "Test exception" in mock_logger.error.call_args[0][0]

    @patch("marimo._save.stores.tiered.LOGGER")
    def test_update_preceding_stores_with_exception(self, mock_logger) -> None:
        """Test handling exceptions during update_preceding_stores operation."""
        store1 = MockStore()
        store1.put = throw_exception
        store2 = MockStore()
        key = "test_key"
        value = b"test_value"
        store2._cache[key] = value

        tiered_store = TieredStore([store1, store2])
        # This should trigger _update_preceding_stores
        result = tiered_store.get(key)

        assert result == value
        mock_logger.error.assert_called_once()
        assert "Test exception" in mock_logger.error.call_args[0][0]
