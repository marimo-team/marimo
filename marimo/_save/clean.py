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
    missing_entries,
    select_blocks,
)
from marimo._save.manifest import (
    ManifestError,
    load_manifest,
    manifest_keys,
    manifest_lock,
    manifest_name,
    manifest_notebook,
)
from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path


@dataclass(frozen=True)
class BlockCleanPlan:
    """The planned clean of whole blocks from one cache directory."""

    cache_dir: Path
    selection: dict[Path, frozenset[str] | None] = field(default_factory=dict)
    freed: CacheDirStats = field(default_factory=CacheDirStats)

    def deletes_nothing(self) -> bool:
        """Whether no file on disk answers to any selected entry."""
        return not self.freed.entries and not self.freed.total_bytes


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
    # Every manifest written for the notebook. After the notebook and its
    # cache directory move, the manifest keeps the name from the old location.
    keys: tuple[str, ...] = ()
    entries: frozenset[tuple[str, str]] = frozenset()
    # Per manifest, the records of the entries that are planned for deletion.
    records: tuple[tuple[str, frozenset[tuple[str, str]]], ...] = ()
    freed: CacheDirStats = field(default_factory=CacheDirStats)
    notes: tuple[str, ...] = ()

    @property
    def tracked(self) -> bool:
        """Whether the cache directory holds a manifest for the notebook."""
        return bool(self.keys)

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
    plans every entry that the notebook's manifests list. An entry that
    another notebook's manifest also lists is kept, because identical code in
    two notebooks produces the same entry.

    Raises:
        ManifestError: If the notebook's manifest cannot be read as one.
        CacheDirError: If a block is a symbolic link.
        OSError: If a manifest or a block cannot be read.
    """
    from marimo._save.stores.file import FileStore

    store = FileStore(save_path=str(cache_dir))
    own_key = manifest_name(notebook)
    notebook = normalize_path(notebook)
    own: dict[str, set[tuple[str, str]]] = {}
    others: set[tuple[str, str]] = set()
    notes: list[str] = []
    for key in manifest_keys(cache_dir):
        try:
            manifest = load_manifest(store, key)
        except ManifestError as e:
            if key == own_key:
                raise
            notes.append(
                f"{key} cannot be read, so the entries that it lists can "
                f"still be deleted: {e}"
            )
            continue
        if manifest is None:
            continue
        if (
            key == own_key
            or manifest_notebook(cache_dir, key, manifest) == notebook
        ):
            own[key] = manifest.entries()
        else:
            others |= manifest.entries()
    if not own:
        return CleanPlan(cache_dir)

    wanted = {block_dir_name(name) for name in names}
    selected = {
        entry
        for entries in own.values()
        for entry in entries
        if not wanted or entry[0] in wanted
    }
    entries = frozenset(selected - others)
    shared = len(selected & others)
    if shared:
        noun = "entry" if shared == 1 else "entries"
        notes.append(f"Kept {shared} {noun} that another notebook also uses.")
    return CleanPlan(
        cache_dir,
        tuple(own),
        entries,
        tuple(
            (key, frozenset(listed & entries)) for key, listed in own.items()
        ),
        delete_cache_entries(cache_dir, entries, dry_run=True),
        tuple(notes),
    )


def apply_clean(plan: CleanPlan) -> CacheDirStats:
    """Carry out `plan`, reporting what it freed.

    A record whose entry cannot be removed is kept, because the entry can
    still be read and deleted later. The manifests are rewritten after the
    entries are gone, so an interrupted run leaves records of missing
    entries rather than entries without a record.

    Raises:
        ManifestError: If a manifest cannot be re-read as one.
        CacheDirError: If a block is a symbolic link.
        OSError: If a block cannot be listed or a manifest cannot be
            rewritten.
    """
    from marimo._save.stores.file import FileStore

    freed = delete_cache_entries(plan.cache_dir, plan.entries)
    store = FileStore(save_path=str(plan.cache_dir))
    # A kernel can write and record entries while this runs, so the records
    # are re-read under the lock and only the planned entries that are gone
    # from disk at that moment are dropped.
    for key, records in plan.records:
        with manifest_lock(store, key):
            manifest = load_manifest(store, key)
            if manifest is None:
                continue
            manifest.discard(missing_entries(plan.cache_dir, records))
            store.put(key, manifest.to_bytes())
    return freed
