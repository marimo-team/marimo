# Copyright 2026 Marimo. All rights reserved.

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


class TestGetStore:
    """get_store reads the store from top-level `[cache].store`."""

    def _store_for(self, monkeypatch, config) -> object:
        from marimo._save import stores as stores_mod

        class _Mgr:
            def get_config(self):
                return config

        monkeypatch.setattr(
            "marimo._config.manager.get_default_config_manager",
            lambda **_kwargs: _Mgr(),
        )
        return stores_mod.get_store()

    def test_top_level_cache_store(self, monkeypatch) -> None:
        store = self._store_for(
            monkeypatch,
            {
                "cache": {
                    "store": {"type": "file", "args": {"save_path": "/tmp/a"}}
                }
            },
        )
        assert isinstance(store, FileStore)
        assert store.save_path.as_posix() == "/tmp/a"

    def test_no_cache_config_uses_default(self, monkeypatch) -> None:
        store = self._store_for(monkeypatch, {})
        assert isinstance(store, DEFAULT_STORE)


class TestCacheStoreProvenance:
    """cache_store_is_untrusted flags a store set by a project/script layer."""

    def _untrusted_for(self, monkeypatch, overrides) -> bool:
        from marimo._save import stores as stores_mod

        class _Mgr:
            def get_config_overrides(self):
                # project + script + env, merged (env never sets a store).
                return overrides

        monkeypatch.setattr(
            "marimo._config.manager.get_default_config_manager",
            lambda **_kwargs: _Mgr(),
        )
        return stores_mod.cache_store_is_untrusted()

    def test_project_store_is_untrusted(self, monkeypatch) -> None:
        assert self._untrusted_for(
            monkeypatch, {"cache": {"store": {"type": "rest"}}}
        )

    def test_script_store_is_untrusted(self, monkeypatch) -> None:
        assert self._untrusted_for(
            monkeypatch, {"cache": {"store": [{"type": "file"}]}}
        )

    def test_no_override_store_is_trusted(self, monkeypatch) -> None:
        # Store set only in the (trusted) user layer never appears in overrides.
        assert not self._untrusted_for(monkeypatch, {})
        assert not self._untrusted_for(
            monkeypatch, {"cache": {"verification": "on"}}
        )
