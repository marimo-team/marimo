# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

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
