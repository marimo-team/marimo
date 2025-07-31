# Copyright 2024 Marimo. All rights reserved.

from __future__ import annotations

from marimo._save.stores import (
    DEFAULT_STORE,
    FileStore,
    TieredStore,
    _get_store_from_config,
)


class TestGetStoreFromConfig:
    def test_none_config(self) -> None:
        """Test that None config returns the default store."""
        store = _get_store_from_config(None)
        assert isinstance(store, DEFAULT_STORE)

    def test_empty_list_config(self) -> None:
        """Test that an empty list config returns the default store."""
        store = _get_store_from_config([])
        assert isinstance(store, DEFAULT_STORE)

    def test_list_with_none_config(self) -> None:
        """Test that a list with None items returns the default store."""
        store = _get_store_from_config([None])
        assert isinstance(store, DEFAULT_STORE)

    def test_single_item_list(self) -> None:
        """Test that a list with a single valid item returns that item's store."""
        config = [{"type": "file", "args": {"save_path": "/tmp/test"}}]
        store = _get_store_from_config(config)
        assert isinstance(store, FileStore)
        assert store.save_path.as_posix() == "/tmp/test"

    def test_multi_item_list(self) -> None:
        """Test that a list with multiple items returns a TieredStore."""
        config = [
            {"type": "file", "args": {"save_path": "/tmp/test1"}},
            {"type": "file", "args": {"save_path": "/tmp/test2"}},
        ]
        store = _get_store_from_config(config)
        assert isinstance(store, TieredStore)
        assert len(store.stores) == 2
        assert all(isinstance(s, FileStore) for s in store.stores)
        assert store.stores[0].save_path.as_posix() == "/tmp/test1"
        assert store.stores[1].save_path.as_posix() == "/tmp/test2"

    def test_dict_config(self) -> None:
        """Test that a dict config returns the appropriate store."""
        config = {"type": "file", "args": {"save_path": "/tmp/test"}}
        store = _get_store_from_config(config)
        assert isinstance(store, FileStore)
        assert store.save_path.as_posix() == "/tmp/test"

    def test_invalid_store_type(self) -> None:
        """Test that an invalid store type returns the default store."""
        config = {"type": "invalid", "args": {}}
        store = _get_store_from_config(config)
        assert isinstance(store, DEFAULT_STORE)

    def test_store_creation_error(self) -> None:
        """Test that an error during store creation returns the default store."""
        config = {"type": "file", "args": {"invalid_arg": "value"}}
        store = _get_store_from_config(config)
        assert isinstance(store, DEFAULT_STORE)

    def test_missing_store_type_uses_default(self) -> None:
        """Test that a missing store type uses the default store type."""
        config = {"args": {}}
        store = _get_store_from_config(config)
        assert isinstance(store, DEFAULT_STORE)
