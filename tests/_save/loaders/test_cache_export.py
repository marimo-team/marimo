# Copyright 2026 Marimo. All rights reserved.
"""Export-cache plumbing: manifest dump, gate, and name derivation.

The end-to-end path (cell caching populates the store, kernel dumps the
manifest on shutdown, exporter bundles it) is exercised once the cache_cells
lifecycle lands. These unit tests cover the pieces in isolation.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from marimo._runtime.callbacks.cache import (
    CacheCallbacks,
    cache_cells_enabled,
)
from marimo._save.loaders import dump_cache_manifests
from marimo._save.loaders.lazy import LazyLoader, LazyStore, _cache_state
from marimo._save.stores.file import FileStore, export_manifest_name

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _clear_loaders() -> None:
    _cache_state().active_lazy_loaders.clear()


def test_export_manifest_name_is_per_notebook() -> None:
    assert export_manifest_name("dir/my nb.py") == ".my-nb-export.json"
    assert export_manifest_name("a/foo.py") != export_manifest_name("a/bar.py")
    # No filename → deterministic fallback, still a hidden json dotfile.
    name = export_manifest_name(None)
    assert name.startswith(".")
    assert name.endswith("-export.json")


def test_dump_cache_manifests_writes_keys(tmp_path: Path) -> None:
    _clear_loaders()
    store = LazyStore(FileStore(save_path=str(tmp_path)))
    LazyLoader("blk", store=store)
    store.put("blk/hash/a.pickle", b"x")
    store.put("blk/hash/return.pickle", b"y")
    try:
        dump_cache_manifests(export_manifest_name("nb.py"))
    finally:
        _clear_loaders()

    manifest = tmp_path / export_manifest_name("nb.py")
    assert manifest.exists()
    assert set(json.loads(manifest.read_text())) == {
        "blk/hash/a.pickle",
        "blk/hash/return.pickle",
    }


def test_dump_cache_manifests_skips_non_file_stores(tmp_path: Path) -> None:
    """In-memory (WASM) stores have nothing on disk — no manifest written."""
    from marimo._save.stores.dict_store import DictStore

    _clear_loaders()
    store = LazyStore(DictStore())
    LazyLoader("blk", store=store)
    store.put("k", b"x")
    try:
        dump_cache_manifests(export_manifest_name("nb.py"))
    finally:
        _clear_loaders()

    assert not (tmp_path / export_manifest_name("nb.py")).exists()


def test_cache_cells_enabled_reads_config() -> None:
    assert cache_cells_enabled({"runtime": {"cache_cells": True}}) is True
    assert cache_cells_enabled({"runtime": {"cache_cells": False}}) is False
    assert cache_cells_enabled({"runtime": {}}) is False
    assert cache_cells_enabled({}) is False


def test_teardown_dumps_only_when_caching_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import marimo._save.loaders as loaders_pkg

    dumped: list[str] = []
    flushed: list[bool] = []
    monkeypatch.setattr(
        loaders_pkg, "dump_cache_manifests", lambda name: dumped.append(name)
    )
    monkeypatch.setattr(
        loaders_pkg, "flush_active_caches", lambda: flushed.append(True)
    )

    on = CacheCallbacks(
        MagicMock(), caching_enabled=lambda: True, notebook_filename="nb.py"
    )
    on.teardown()
    assert flushed == [True]
    assert dumped == [export_manifest_name("nb.py")]

    dumped.clear()
    flushed.clear()
    off = CacheCallbacks(
        MagicMock(), caching_enabled=lambda: False, notebook_filename="nb.py"
    )
    off.teardown()
    # Flush still runs (durability); the manifest dump does not.
    assert flushed == [True]
    assert dumped == []
