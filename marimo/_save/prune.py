# Copyright 2026 Marimo. All rights reserved.
"""Plan and carry out `marimo cache prune`, one cache directory at a time.

A manifest records each entry under the path hash of the cell that produced
it. A path hash is a digest of that cell and everything that the cell
depends on, and compiling the notebook recomputes it. An entry that no live
path hash lists came from code that is gone.

The rule is one-sided. Prune never deletes an entry that a manifest records
under code that still exists, and deleting an entry that code can still
reuse costs a recomputation rather than a wrong answer. When a manifest fails to parse
or a notebook fails to compile, every entry that it covers is kept.

Prune also deletes a directory of blobs whose marker is gone, because
nothing reads it any more, whether a manifest tracks it or none does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._save.cache_dirs import (
    CacheDirStats,
    cache_entry_keys,
    delete_blob_dirs,
    delete_cache_entries,
    entry_hash,
    missing_entries,
    orphan_blob_dirs,
    remove_empty_blocks,
)
from marimo._save.manifest import (
    CacheManifest,
    ManifestError,
    is_manifest_name,
    load_manifest,
    manifest_lock,
    manifest_name,
)
from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from pathlib import Path

LOGGER = _loggers.marimo_logger()

NO_MANIFEST = "No manifest records this cache, so its entries are kept."


@dataclass(frozen=True)
class PrunePlan:
    """The planned prune of one cache directory."""

    cache_dir: Path
    # Tracked entries that no live path hash lists.
    entries: frozenset[tuple[str, str]] = frozenset()
    # Per block, the directories of blobs that no marker reads, or `None`
    # for a block that cannot be listed. The cache root is the blank block.
    orphans: dict[str, frozenset[str] | None] = field(default_factory=dict)
    # Per manifest, the records of the entries that the plan deletes. A dead
    # entry that another manifest keeps alive stays recorded, because the
    # entry stays.
    records: tuple[tuple[str, frozenset[tuple[str, str]]], ...] = ()
    freed: CacheDirStats = field(default_factory=CacheDirStats)
    dead_nodes: int = 0
    untracked: int = 0
    # Why parts of the directory are kept.
    notes: tuple[str, ...] = ()

    def deletes_nothing(self) -> bool:
        """Whether no file on disk answers to anything planned."""
        return not self.freed.entries and not self.freed.total_bytes

    def forgets(self) -> int:
        """How many records the plan removes from the manifests."""
        return sum(len(records) for _, records in self.records)


def plan_prune(cache_dir: Path, *, force: bool = False) -> PrunePlan:
    """Plan the prune of `cache_dir`, deleting nothing.

    With `force`, directories of blobs at the cache root that no marker
    reads are planned too, each with a note naming it.

    Raises:
        CacheDirError: If a block of a tracked entry is a symbolic link.
        OSError: If such a block cannot be listed.
    """
    from marimo._save.stores.file import FileStore

    orphans = orphan_blob_dirs(cache_dir, root=force)
    root_notes = [
        f"{name} at the cache root holds blobs that no entry reads."
        for name in sorted(orphans.get("") or ())
    ]
    keys = _manifest_keys(cache_dir)
    if not keys:
        no_manifest = [NO_MANIFEST] if cache_dir.is_dir() else []
        return PrunePlan(
            cache_dir,
            orphans=orphans,
            freed=delete_blob_dirs(cache_dir, orphans, dry_run=True),
            notes=tuple(no_manifest + root_notes),
        )

    store = FileStore(save_path=str(cache_dir))
    recorded: set[tuple[str, str]] = set()
    evicted: set[tuple[str, str]] = set()
    live: set[tuple[str, str]] = set()
    records: dict[str, set[tuple[str, str]]] = {}
    notes: list[str] = root_notes
    dead_nodes = 0
    readable = True
    for key in keys:
        try:
            manifest = load_manifest(store, key)
        except (ManifestError, OSError) as e:
            # Bytes that do not parse as a manifest can still list entries
            # under live code, so no tracked entry is deleted on the word of
            # another manifest.
            notes.append(
                f"{key} cannot be read, so every tracked entry is kept: {e}"
            )
            readable = False
            continue
        if manifest is None:
            continue

        entries = manifest.entries()
        recorded |= entries
        # Blobs that nothing reads are deleted whichever path hash records
        # them.
        records[key] = {
            (block, entry)
            for block, entry in entries
            if entry_hash(entry) in (orphans.get(block) or ())
        }
        notebook = _manifest_notebook(cache_dir, key, manifest)
        if notebook is None:
            notes.append(
                f"{key} does not say which notebook wrote it, so its entries "
                "are kept."
            )
            live |= entries
            continue
        live_nodes = _live_nodes(notebook)
        if live_nodes is None:
            notes.append(
                f"{notebook.name} does not read as a whole notebook, so its "
                "entries are kept."
            )
            live |= entries
            continue

        before = len(manifest.nodes)
        dead = manifest.evict_dead(live_nodes)
        dead_nodes += before - len(manifest.nodes)
        evicted |= dead
        live |= manifest.entries()
        records[key] |= dead

    # An entry that another manifest lists under live code is reachable
    # through it, and one that no manifest lists is not this command's to
    # delete.
    doomed = frozenset(evicted - live) if readable else frozenset()
    freed = delete_cache_entries(cache_dir, doomed, dry_run=True)
    freed += delete_blob_dirs(cache_dir, orphans, dry_run=True)
    forgettable = {
        key: {
            entry
            for entry in entries
            if entry in doomed
            or entry_hash(entry[1]) in (orphans.get(entry[0]) or ())
            or entry in missing_entries(cache_dir, entries)
        }
        for key, entries in records.items()
    }
    return PrunePlan(
        cache_dir=cache_dir,
        entries=doomed,
        orphans=orphans,
        records=tuple(
            (key, frozenset(entries))
            for key, entries in sorted(forgettable.items())
            if entries
        ),
        freed=freed,
        dead_nodes=dead_nodes,
        untracked=len(cache_entry_keys(cache_dir) - recorded),
        notes=tuple(notes),
    )


def apply_prune(plan: PrunePlan) -> CacheDirStats:
    """Carry out `plan`, reporting what it freed.

    Entries are deleted before their records, so an interrupted run leaves
    records of missing entries rather than entries without a record. A
    record whose entry cannot be removed is kept, so the deletion can be
    retried.

    A path that cannot be listed or removed counts as a failure in the
    returned stats.

    Raises:
        ManifestError: If a manifest cannot be re-read as one.
        CacheDirError: If a block is a symbolic link.
        OSError: If a block cannot be listed or a manifest cannot be
            rewritten.
    """
    from marimo._save.stores.file import FileStore

    freed = delete_cache_entries(plan.cache_dir, plan.entries)
    freed += delete_blob_dirs(plan.cache_dir, plan.orphans)
    # A block that cannot be listed is counted as a failure already.
    freed += remove_empty_blocks(
        plan.cache_dir,
        {block for block, _ in plan.entries}
        | {block for block, hashes in plan.orphans.items() if hashes},
    )
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


def _manifest_keys(cache_dir: Path) -> list[str]:
    """The manifests held at the root of `cache_dir`."""
    # A cache that was never written is the ordinary case, not a failure to
    # read one.
    if not cache_dir.is_dir():
        return []
    try:
        children = list(cache_dir.iterdir())
    except OSError as e:
        LOGGER.warning("Skipping %s: %s", cache_dir, e)
        return []
    return sorted(
        child.name
        for child in children
        if child.is_file() and is_manifest_name(child.name)
    )


def _manifest_notebook(
    cache_dir: Path, key: str, manifest: CacheManifest
) -> Path | None:
    """The notebook `manifest` was written for, or `None` if it is foreign.

    A manifest records where its notebook was, relative to the cache
    directory. Its name is taken from where that notebook was in full. A
    record that no longer names the manifest holding it describes a tree
    that later moved, so it does not say which source to read for liveness.
    """
    if not manifest.notebook:
        return None
    notebook = normalize_path(cache_dir / manifest.notebook)
    if manifest_name(notebook) != key:
        return None
    return notebook


def _live_nodes(notebook: Path) -> set[str] | None:
    """The path hash of every cell `notebook` still holds.

    A notebook that is gone holds no cells and so lists nothing, which is
    what makes a deleted notebook's entries prunable. `None` means that the
    notebook cannot be read whole, because it did not compile or it parsed
    with errors that can drop a cell. What it holds is then unknown, never
    empty.
    """
    from marimo._ast.app import InternalApp
    from marimo._ast.load import get_notebook_status, load_notebook_ir
    from marimo._save.hash import hash_cell_closure

    if not notebook.is_file():
        return set()
    try:
        status = get_notebook_status(str(notebook))
    except Exception:
        LOGGER.warning("Could not read %s", notebook, exc_info=True)
        return None
    if status.status == "empty":
        # A file emptied to nothing, or to comments and a docstring, holds
        # no code that can produce an entry.
        return set()
    if (
        status.status not in ("valid", "has_warnings")
        or status.notebook is None
    ):
        # A parse with errors can leave out a cell that Python still runs,
        # and a missing cell reads as dead code.
        return None
    if not status.notebook.valid:
        # Reads as a notebook but holds no app, so its cells are not what
        # running the file executes.
        return None

    try:
        graph = InternalApp(load_notebook_ir(status.notebook)).graph
    except Exception:
        LOGGER.warning("Could not compile %s", notebook, exc_info=True)
        return None
    if len(graph.cells) != len(status.notebook.cells):
        # A cell that does not compile drops out of the graph rather than
        # raising, and its absence reads as code that is gone. So does the
        # path hash of every cell below it.
        LOGGER.warning("Not every cell of %s compiles", notebook)
        return None
    return {hash_cell_closure(cell_id, graph).hex() for cell_id in graph.cells}
