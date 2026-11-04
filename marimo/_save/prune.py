# Copyright 2026 Marimo. All rights reserved.
"""Apply `marimo cache prune`

Uses the manifest records for each notebook/cell to determine stale cache entries,
and "prunes" them to the bare closure of needed results.
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
    """The planned prune of one cache directory.

    The fields follow `CleanPlan`. `entries` are the tracked entries to
    delete, and `freed` is what deleting them is expected to free. `orphans`
    selects directories of blobs by block, in the shape of
    `BlockCleanPlan.selection`.
    """

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
    # Directories of blobs that a partial marker claims for a writer.
    claimed: int = 0
    # Whether claimed directories and the cache root are pruned too.
    force: bool = False
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
    reads are planned too, each with a note naming it, and so are the
    directories that a partial marker claims for a writer.

    A cache directory that cannot be listed is planned as one failure.

    Raises:
        CacheDirError: If a block of a tracked entry is a symbolic link.
        OSError: If such a block cannot be listed.
    """
    from marimo._save.stores.file import FileStore

    try:
        keys = _manifest_keys(cache_dir)
    except OSError as e:
        # Planned as a root that cannot be listed, so the failure is counted
        # again when the plan is applied.
        LOGGER.warning("Could not list %s: %s", cache_dir, e)
        unlisted: dict[str, frozenset[str] | None] = {"": None}
        return PrunePlan(
            cache_dir,
            orphans=unlisted,
            freed=delete_blob_dirs(cache_dir, unlisted, dry_run=True),
            force=force,
        )
    scan = orphan_blob_dirs(cache_dir, root=force, force=force)
    orphans = scan.selection
    root_notes = [
        f"{name} at the cache root holds blobs that no entry reads."
        for name in sorted(orphans.get("") or ())
    ]
    if not keys:
        no_manifest = [NO_MANIFEST] if cache_dir.is_dir() else []
        return PrunePlan(
            cache_dir,
            orphans=orphans,
            freed=delete_blob_dirs(
                cache_dir, orphans, dry_run=True, force=force
            ),
            claimed=scan.claimed,
            force=force,
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
            if (cache_dir / key).exists():
                # A manifest truncated to nothing lists nothing, unlike one
                # removed since the listing, so what it protected is unknown.
                notes.append(
                    f"{key} cannot be read, so every tracked entry is kept: "
                    "it holds no records."
                )
                readable = False
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
    claimed = scan.claimed
    if not force:
        # A writer that is rewriting a dead entry claimed its blobs.
        held = frozenset(
            entry
            for entry in doomed
            if entry_hash(entry[1]) in scan.claims.get(entry[0], ())
        )
        doomed -= held
        claimed += len(held)
    freed = delete_cache_entries(
        cache_dir,
        doomed,
        dry_run=True,
        protect_claims=not force,
        sweep_claims=force,
    )
    freed += delete_blob_dirs(cache_dir, orphans, dry_run=True, force=force)
    forgettable: dict[str, set[tuple[str, str]]] = {}
    for key, entries in records.items():
        missing = missing_entries(cache_dir, entries)
        forgettable[key] = {
            entry
            for entry in entries
            if entry in doomed
            or entry_hash(entry[1]) in (orphans.get(entry[0]) or ())
            or entry in missing
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
        claimed=claimed,
        force=force,
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

    # Orphans go first. Their block must still hold an entry when they are
    # checked again, and the planned entries can be the last ones in it.
    freed = delete_blob_dirs(plan.cache_dir, plan.orphans, force=plan.force)
    freed += delete_cache_entries(
        plan.cache_dir,
        plan.entries,
        protect_claims=not plan.force,
        sweep_claims=plan.force,
    )
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
    """The manifests held at the root of `cache_dir`.

    Raises:
        OSError: If `cache_dir` cannot be listed.
    """
    # A cache that was never written is the ordinary case, not a failure to
    # read one.
    if not cache_dir.is_dir():
        return []
    return sorted(
        child.name
        for child in cache_dir.iterdir()
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

    try:
        notebook.stat()
    except FileNotFoundError:
        return set()
    except OSError:
        # A notebook that cannot be reached is not one that is gone.
        LOGGER.warning("Could not read %s", notebook, exc_info=True)
        return None
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
