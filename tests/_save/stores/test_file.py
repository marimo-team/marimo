# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from pathlib import Path

import marimo._save.stores.file as file_mod
from marimo._save.stores.file import FileStore


class TestFileStore:
    def test_init_doesnt_make_file(self, tmp_path) -> None:
        """Test that initializing FileStore does not create a file."""
        _store = FileStore(tmp_path / "test_store")
        # Should not be created just on initialization
        assert not (tmp_path / "test_store").exists()

    def test_get_put(self, tmp_path) -> None:
        """Test put and get functionality of FileStore."""
        store = FileStore(tmp_path / "test_store")
        assert not (tmp_path / "test_store").exists()
        data = b"hello world"
        store.put("key", data)
        assert store.get("key") == data
        # Store is actually created
        assert (tmp_path / "test_store").exists()
        assert (tmp_path / "test_store" / "key").exists()

    def test_clear(self, tmp_path) -> None:
        """Test clear functionality of FileStore."""
        store = FileStore(tmp_path / "test_store")
        data = b"test data"

        # Put some data
        store.put("key1", data)
        assert store.hit("key1")
        assert store.get("key1") == data

        # Clear the key
        result = store.clear("key1")
        assert result is True
        assert not store.hit("key1")
        assert store.get("key1") is None

        # Clear non-existent key
        result = store.clear("nonexistent")
        assert result is False

    def test_default_path_is_lazy(self) -> None:
        """Default save_path is not resolved at construction time."""
        store = FileStore()
        # The backing attribute should be None until first access.
        assert store._resolved_save_path is None
        # Accessing the property triggers resolution.
        _ = store.save_path
        assert store._resolved_save_path is not None


class TestDefaultSavePath:
    def test_writable_notebook_dir(self, tmp_path, monkeypatch) -> None:
        """The cache anchors next to the notebook when its directory is writable."""
        monkeypatch.setattr(file_mod, "notebook_dir", lambda: tmp_path)

        path = FileStore()._default_save_path()

        assert path == tmp_path / "__marimo__" / "cache"

    def test_read_only_notebook_dir_falls_back_to_cwd(
        self, tmp_path, monkeypatch
    ) -> None:
        """A read-only notebook directory anchors the cache to the working directory."""
        monkeypatch.setattr(file_mod, "notebook_dir", lambda: tmp_path)
        monkeypatch.setattr(file_mod.os, "access", lambda *_args: False)

        path = FileStore()._default_save_path()

        assert path == Path("__marimo__", "cache")
