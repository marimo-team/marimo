# Copyright 2026 Marimo. All rights reserved.
"""Plan and carry out `marimo cache clean`, one cache directory at a time."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._save.cache_dirs import (
    CacheDirStats,
    block_dir_name,
    delete_blocks,
    delete_cache_entries,
    holds_entry,
    select_blocks,
)
from marimo._save.manifest import (
    CacheManifest,
    load_manifest,
    manifest_lock,
    manifest_name,
)

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path


@dataclass(frozen=True)
class BlockCleanPlan:
    """The planned clean of whole blocks from one cache directory."""

    cache_dir: Path
    selection: dict[Path, frozenset[str]] = field(default_factory=dict)
    freed: CacheDirStats = field(default_factory=CacheDirStats)


def plan_block_clean(
    cache_dir: Path, names: Collection[str] = ()
) -> BlockCleanPlan:
    """Plan the clean of the blocks `names` in `cache_dir`, deleting nothing.

    An empty `names` plans every block.
    """
    selection = select_blocks(cache_dir, names)
    return BlockCleanPlan(
        cache_dir, selection, delete_blocks(cache_dir, selection, dry_run=True)
    )


def apply_block_clean(plan: BlockCleanPlan) -> CacheDirStats:
    """Carry out `plan`, reporting what it freed.

    Entries written since the plan was made are left alone.
    """
    return delete_blocks(plan.cache_dir, plan.selection)


@dataclass(frozen=True)
class CleanPlan:
    """The planned clean of one notebook's entries in one cache directory."""

    cache_dir: Path
    key: str
    manifest: CacheManifest | None = None
    entries: frozenset[tuple[str, str]] = frozenset()
    freed: CacheDirStats = field(default_factory=CacheDirStats)

    @property
    def tracked(self) -> bool:
        """Whether the cache directory holds a manifest for the notebook."""
        return self.manifest is not None

    def deletes_nothing(self) -> bool:
        """Whether no file on disk answers to any planned entry.

        Such records hold nothing, so forgetting them takes nothing away
        from the cache.
        """
        return not self.freed.entries and not self.freed.total_bytes


def plan_clean(
    cache_dir: Path, notebook: Path, names: Collection[str] = ()
) -> CleanPlan:
    """Plan the clean of `notebook`'s entries in `cache_dir`, deleting nothing.

    `names` are the names given to `mo.persistent_cache`. An empty `names`
    plans every entry the manifest lists.

    Raises:
        ManifestError: If the manifest cannot be read as one.
        OSError: If the manifest cannot be read at all.
    """
    from marimo._save.stores.file import FileStore

    key = manifest_name(notebook)
    manifest = None
    if cache_dir.is_dir():
        manifest = load_manifest(FileStore(save_path=str(cache_dir)), key)
    if manifest is None:
        return CleanPlan(cache_dir, key)

    entries = manifest.entries()
    if names:
        wanted = {block_dir_name(name) for name in names}
        entries = {entry for entry in entries if entry[0] in wanted}
    return CleanPlan(
        cache_dir,
        key,
        manifest,
        frozenset(entries),
        delete_cache_entries(cache_dir, entries, dry_run=True),
    )


def apply_clean(plan: CleanPlan) -> CacheDirStats:
    """Carry out `plan`, reporting what it freed.

    A record whose entry cannot be removed is kept, because the entry can
    still be read and deleted later. The manifest is rewritten after the
    entries are gone, so an interrupted run leaves records of missing
    entries rather than entries without a record.

    Raises:
        ManifestError: If the manifest cannot be re-read as one.
        OSError: If a block cannot be listed or the manifest cannot be
            rewritten.
    """
    from marimo._save.stores.file import FileStore

    if plan.manifest is None:
        return CacheDirStats()
    freed = delete_cache_entries(plan.cache_dir, plan.entries)
    store = FileStore(save_path=str(plan.cache_dir))
    # A kernel can write and record entries while this runs, so the records
    # are re-read under the lock and only the planned entries that are gone
    # from disk at that moment are dropped.
    with manifest_lock(store, plan.key):
        manifest = load_manifest(store, plan.key)
        if manifest is None:
            return freed
        manifest.discard(
            {
                entry
                for entry in plan.entries
                if not holds_entry(plan.cache_dir, *entry)
            }
        )
        store.put(plan.key, manifest.to_bytes())
    return freed
