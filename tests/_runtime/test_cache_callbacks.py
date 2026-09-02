# Copyright 2026 Marimo. All rights reserved.
"""Cache statistics reported to the cache panel."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import marimo._runtime.callbacks.cache as cache_callbacks
from marimo._runtime.callbacks.cache import CacheCallbacks
from marimo._runtime.commands import ClearCacheCommand, GetCacheInfoCommand
from marimo._runtime.state import State
from marimo._save.cache import CacheContext
from marimo._save.loaders.lazy import LazyLoader, LazyStore
from marimo._save.loaders.memory import MemoryLoader
from marimo._save.loaders.pickle import PickleLoader
from marimo._save.stores.file import FileStore

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from marimo._messaging.notification import CacheInfoNotification
    from marimo._save.loaders.loader import Loader


class FakeCache(CacheContext):
    """A cache as the notebook's globals hold one, without a kernel."""

    __slots__ = ()

    def __init__(self, loader: Loader | None) -> None:
        self._loader = None if loader is None else State(loader)

    @property
    def last_hash(self) -> str | None:
        return None


def make_cache(cache_dir: Path, block: str) -> FakeCache:
    return FakeCache(PickleLoader(block, store=FileStore(str(cache_dir))))


def write_entry(cache_dir: Path, block: str, name: str, size: int) -> None:
    entry = cache_dir / block / name
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_bytes(b"x" * size)


def capture_notifications(
    monkeypatch: pytest.MonkeyPatch,
) -> list[CacheInfoNotification]:
    sent: list[Any] = []
    monkeypatch.setattr(cache_callbacks, "broadcast_notification", sent.append)
    return sent


async def test_get_cache_info_measures_the_loaders_cache_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "__marimo__" / "cache"
    write_entry(cache_dir, "train", "C_ab12.pickle", 100)
    # A block no cache in scope owns. It counts as disk used, but purging
    # the notebook's caches does not free it.
    write_entry(cache_dir, "stale", "C_77e0.pickle", 40)
    scope = SimpleNamespace(globals={"train": make_cache(cache_dir, "train")})
    sent = capture_notifications(monkeypatch)

    callbacks = CacheCallbacks(
        scope, notebook_filename=str(tmp_path / "nb.py")
    )
    await callbacks.get_cache_info(GetCacheInfoCommand())

    assert len(sent) == 1
    assert sent[0].disk_total == 140
    assert sent[0].disk_to_free == 100


async def test_get_cache_info_follows_a_custom_save_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `save_path=` moves a cache off the notebook-adjacent directory, and a
    # same-named block left behind there belongs to no cache in scope.
    elsewhere = tmp_path / "scratch"
    write_entry(elsewhere, "train", "C_ab12.pickle", 100)
    write_entry(tmp_path / "__marimo__" / "cache", "train", "C_77e0.pickle", 7)
    scope = SimpleNamespace(globals={"train": make_cache(elsewhere, "train")})
    sent = capture_notifications(monkeypatch)

    callbacks = CacheCallbacks(
        scope, notebook_filename=str(tmp_path / "nb.py")
    )
    await callbacks.get_cache_info(GetCacheInfoCommand())

    assert sent[0].disk_total == 100
    assert sent[0].disk_to_free == 100


async def test_get_cache_info_reports_no_disk_for_a_memory_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An in-memory cache holds no disk, whatever a directory of the same name
    # beside the notebook happens to hold.
    cache_dir = tmp_path / "__marimo__" / "cache"
    write_entry(cache_dir, "train", "C_ab12.pickle", 100)
    scope = SimpleNamespace(
        globals={"train": FakeCache(MemoryLoader("train", max_size=10))}
    )
    sent = capture_notifications(monkeypatch)

    callbacks = CacheCallbacks(
        scope, notebook_filename=str(tmp_path / "nb.py")
    )
    await callbacks.get_cache_info(GetCacheInfoCommand())

    assert sent[0].disk_total == 0
    assert sent[0].disk_to_free == 0


async def test_get_cache_info_promises_only_what_purging_frees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "__marimo__" / "cache"
    write_entry(cache_dir, "train", "C_ab12.pickle", 100)
    # A value too large to inline is stored as a directory of blobs, which
    # purging leaves behind.
    write_entry(cache_dir, "train", "ab12/return.npy", 500)
    cache = make_cache(cache_dir, "train")
    scope = SimpleNamespace(globals={"train": cache})
    sent = capture_notifications(monkeypatch)

    callbacks = CacheCallbacks(
        scope, notebook_filename=str(tmp_path / "nb.py")
    )
    await callbacks.get_cache_info(GetCacheInfoCommand())
    await callbacks.clear_cache(ClearCacheCommand())
    await callbacks.get_cache_info(GetCacheInfoCommand())

    promised = sent[0].disk_to_free
    assert promised == sent[0].disk_total - sent[-1].disk_total
    assert sent[-1].disk_to_free == 0


async def test_get_cache_info_promises_the_blobs_of_a_lazy_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A lazy cache stores through a wrapper around a file store, which its
    # loader still clears by path, blobs and all.
    cache_dir = tmp_path / "__marimo__" / "cache"
    write_entry(cache_dir, "cell_cache", "P_ab12.jsonl", 100)
    write_entry(cache_dir, "cell_cache", "ab12/return.npy", 500)
    loader = LazyLoader(
        "cell_cache",
        store=LazyStore(FileStore(str(cache_dir))),
        verification="off",
    )
    scope = SimpleNamespace(globals={"cell_cache": FakeCache(loader)})
    sent = capture_notifications(monkeypatch)

    callbacks = CacheCallbacks(
        scope, notebook_filename=str(tmp_path / "nb.py")
    )
    await callbacks.get_cache_info(GetCacheInfoCommand())
    await callbacks.clear_cache(ClearCacheCommand())
    await callbacks.get_cache_info(GetCacheInfoCommand())

    assert sent[0].disk_total == 600
    assert sent[0].disk_to_free == 600
    assert sent[-1].disk_total == 0
    assert sent[-1].disk_to_free == 0


async def test_get_cache_info_ignores_a_cache_without_a_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `mo.cache(pin_modules=True)` assigned to a name is a cache waiting for
    # a function. Reading its loader raises.
    cache_dir = tmp_path / "__marimo__" / "cache"
    write_entry(cache_dir, "train", "C_ab12.pickle", 100)
    cache = make_cache(cache_dir, "train")
    cache.loader._hits = 3
    scope = SimpleNamespace(
        globals={"train": cache, "unbound": FakeCache(None)}
    )
    sent = capture_notifications(monkeypatch)

    callbacks = CacheCallbacks(
        scope, notebook_filename=str(tmp_path / "nb.py")
    )
    await callbacks.get_cache_info(GetCacheInfoCommand())

    assert len(sent) == 1
    assert sent[0].hits == 3
    assert sent[0].disk_total == 100


async def test_get_cache_info_when_the_cache_cannot_be_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unreadable(cache_dir: Path) -> None:
        raise OSError(f"Cannot read {cache_dir}")

    monkeypatch.setattr("marimo._save.cache_dirs.cache_dir_stats", unreadable)
    cache_dir = tmp_path / "__marimo__" / "cache"
    write_entry(cache_dir, "train", "C_ab12.pickle", 100)
    cache = make_cache(cache_dir, "train")
    cache.loader._hits = 2
    scope = SimpleNamespace(globals={"train": cache})
    sent = capture_notifications(monkeypatch)

    callbacks = CacheCallbacks(
        scope, notebook_filename=str(tmp_path / "nb.py")
    )
    await callbacks.get_cache_info(GetCacheInfoCommand())

    assert len(sent) == 1
    assert sent[0].hits == 2
    assert sent[0].disk_total == 0
    assert sent[0].disk_to_free == 0


async def test_get_cache_info_without_a_notebook_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A notebook run from a buffer has no path to derive a cache directory
    # from. The loader still knows where it writes.
    cache_dir = tmp_path / "__marimo__" / "cache"
    write_entry(cache_dir, "train", "C_ab12.pickle", 100)
    cache = make_cache(cache_dir, "train")
    cache.loader._hits = 3
    scope = SimpleNamespace(globals={"train": cache})
    sent = capture_notifications(monkeypatch)

    await CacheCallbacks(scope).get_cache_info(GetCacheInfoCommand())

    assert sent[0].hits == 3
    assert sent[0].disk_total == 100
    assert sent[0].disk_to_free == 100
