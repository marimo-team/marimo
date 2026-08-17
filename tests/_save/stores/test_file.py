# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import logging
from pathlib import Path

import marimo._save.stores.file as file_mod
from marimo import _loggers
from marimo._save.stores.file import FileStore


def _propagate_marimo_logs(monkeypatch) -> None:
    """Let `caplog` see marimo's logger, which does not propagate by default."""
    monkeypatch.setattr(_loggers.marimo_logger(), "propagate", True)


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

    def test_unwritable_target_falls_back_to_cwd(
        self, tmp_path, monkeypatch
    ) -> None:
        """A cache directory that cannot be created anchors to the working directory."""
        monkeypatch.setattr(file_mod, "notebook_dir", lambda: tmp_path)

        def deny_mkdir(self: Path, *_args: object, **_kwargs: object) -> None:
            raise PermissionError(f"read-only: {self}")

        monkeypatch.setattr(Path, "mkdir", deny_mkdir)

        path = FileStore()._default_save_path()

        assert path == Path("__marimo__", "cache")

    def test_existing_read_only_target_falls_back_to_cwd(
        self, tmp_path, monkeypatch
    ) -> None:
        """An existing cache directory that is not writable anchors to the working directory."""
        monkeypatch.setattr(file_mod, "notebook_dir", lambda: tmp_path)
        (tmp_path / "__marimo__" / "cache").mkdir(parents=True)
        monkeypatch.setattr(file_mod.os, "access", lambda *_args: False)

        path = FileStore()._default_save_path()

        assert path == Path("__marimo__", "cache")

    def test_fallback_is_warned_about(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """The warning names both directories.

        Otherwise the move reads as a cache miss.
        """
        monkeypatch.setattr(file_mod, "notebook_dir", lambda: tmp_path)
        (tmp_path / "__marimo__" / "cache").mkdir(parents=True)
        monkeypatch.setattr(file_mod.os, "access", lambda *_args: False)
        _propagate_marimo_logs(monkeypatch)

        with caplog.at_level(logging.WARNING):
            FileStore()._default_save_path()

        assert str(tmp_path / "__marimo__" / "cache") in caplog.text
        assert str(Path("__marimo__", "cache").resolve()) in caplog.text

    def test_unnamed_notebook_does_not_warn(self, monkeypatch, caplog) -> None:
        """No warning: an unnamed notebook never had a directory to leave."""
        monkeypatch.setattr(file_mod, "notebook_dir", lambda: None)
        _propagate_marimo_logs(monkeypatch)

        with caplog.at_level(logging.WARNING):
            path = FileStore()._default_save_path()

        assert path == Path("__marimo__", "cache")
        assert caplog.text == ""
