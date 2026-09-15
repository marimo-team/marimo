# Copyright 2026 Marimo. All rights reserved.
"""Deletion of the cache entries that current code can no longer produce.

A manifest records each entry under the path hash of the cell that produced
it. A path hash is a digest of that cell and everything it depends on.
Compiling the notebook recomputes it. An entry that no compiled hash lists
can only have come from code that is gone.

The rule is one-sided. An entry recorded under code that still exists is
never deleted, and deleting one that code can still reuse costs a
recomputation rather than a wrong answer. Anything that cannot be read as
evidence protects what it covers instead of guessing: a directory with no
manifest, a manifest that will not parse, a notebook that will not compile.

Pure and kernel-free so the CLI can import it without starting a runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._save.cache_dirs import (
    CacheDirStats,
    cache_entry_keys,
    delete_cache_entries,
    directory_cache_dir,
    is_marimo_notebook,
)
from marimo._save.manifest import (
    CacheManifest,
    ManifestError,
    is_manifest_name,
    load_manifest,
    manifest_name,
)
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable
    from pathlib import Path

LOGGER = _loggers.marimo_logger()

NO_MANIFEST = "Nothing records what wrote this cache, so nothing is pruned."

# sys.pycache_prefix moves a cache away from the notebooks that write it,
# so there is no directory to enumerate the notebooks from.
SIBLINGS_UNVERIFIABLE = (
    "This cache does not sit beside the notebooks that write it, so a "
    "notebook sharing it cannot be checked for a manifest."
)


@dataclass(frozen=True)
class DirectoryPrunePlan:
    """The planned prune of one cache directory."""

    cache_dir: Path
    # The entries to delete, and what deleting them is expected to free.
    entries: frozenset[tuple[str, str]] = frozenset()
    freed: CacheDirStats = field(default_factory=CacheDirStats)
    # Manifests to write back, each already without its dead path hashes.
    rewrites: tuple[tuple[str, CacheManifest], ...] = ()
    dead_nodes: int = 0
    untracked: int = 0
    # Why part of the directory was left alone, and what has to be agreed to
    # before the rest of it is pruned.
    skips: tuple[str, ...] = ()
    confirmations: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        """Whether applying this plan changes nothing."""
        return not self.entries and not self.rewrites

    def needs_approval(self) -> bool:
        """Whether deleting from this directory has to be agreed to first.

        The reasons are reported whether or not they hold anything up. Only
        a deletion is gated on them.
        """
        return bool(self.entries) and bool(self.confirmations)


@dataclass(frozen=True)
class PrunePlan:
    """The planned prune of every directory a path resolved to."""

    directories: tuple[DirectoryPrunePlan, ...] = ()

    @property
    def freed(self) -> CacheDirStats:
        total = CacheDirStats()
        for directory in self.directories:
            total += directory.freed
        return total


def plan_prune(cache_dirs: Iterable[Path]) -> PrunePlan:
    """Plan the prune of `cache_dirs` without deleting anything."""
    return PrunePlan(
        tuple(_plan_directory(cache_dir) for cache_dir in cache_dirs)
    )


def apply_prune(plan: PrunePlan) -> CacheDirStats:
    """Carry out `plan`, reporting what it freed.

    Entries are deleted before the manifests that list them are rewritten,
    so a run that dies midway leaves records of entries the cache no longer
    holds rather than entries nothing records.
    """
    freed = CacheDirStats()
    for directory in plan.directories:
        freed += delete_cache_entries(directory.cache_dir, directory.entries)
        _rewrite_manifests(directory)
    return freed


def _plan_directory(cache_dir: Path) -> DirectoryPrunePlan:
    from marimo._save.stores.file import FileStore

    keys = _manifest_keys(cache_dir)
    if not keys:
        return DirectoryPrunePlan(cache_dir, skips=(NO_MANIFEST,))

    store = FileStore(save_path=str(cache_dir))
    attested: set[tuple[str, str]] = set()
    evicted: set[tuple[str, str]] = set()
    live: set[tuple[str, str]] = set()
    rewrites: list[tuple[str, CacheManifest]] = []
    skips: list[str] = []
    confirmations: list[str] = []
    dead_nodes = 0

    for key in keys:
        try:
            manifest = load_manifest(store, key)
        except ManifestError as e:
            # Bytes that read as no manifest list nothing, so deleting the
            # entries they cover rests on another manifest's word alone.
            confirmations.append(f"{key} cannot be read: {e}")
            continue
        if manifest is None:
            # A manifest an interrupted write left empty is in the same
            # position: named after a notebook, holding none of its records.
            confirmations.append(f"{key} holds no records.")
            continue

        attested |= manifest.entries()
        notebook = _manifest_notebook(cache_dir, key, manifest)
        if notebook is None:
            skips.append(
                f"{key} does not say which notebook wrote it, so its entries "
                "are kept."
            )
            live |= manifest.entries()
            continue

        live_nodes = _live_nodes(notebook)
        if live_nodes is None:
            skips.append(
                f"{notebook.name} does not compile, so its entries are kept."
            )
            live |= manifest.entries()
            continue

        before = len(manifest.nodes)
        evicted |= manifest.evict_dead(live_nodes)
        live |= manifest.entries()
        if len(manifest.nodes) != before:
            dead_nodes += before - len(manifest.nodes)
            rewrites.append((key, manifest))

    # An entry another manifest still lists is reachable through it, and one
    # no manifest lists at all was never this command's to delete.
    doomed = frozenset(evicted - live)
    if doomed:
        # A notebook that shares the cache only stands in the way of a
        # deletion, and looking for one costs a directory listing.
        confirmations += _unattested_siblings(cache_dir, keys)
    return DirectoryPrunePlan(
        cache_dir=cache_dir,
        entries=doomed,
        freed=delete_cache_entries(cache_dir, doomed, dry_run=True),
        rewrites=tuple(rewrites),
        dead_nodes=dead_nodes,
        untracked=len(cache_entry_keys(cache_dir) - attested),
        skips=tuple(skips),
        confirmations=tuple(confirmations),
    )


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
    that later moved, and says nothing about which source to read liveness
    from.
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
    what makes a deleted notebook's entries prunable. `None` says the
    notebook did not compile. What it holds is then unknown, never empty.
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
    if status.status == "invalid":
        return None
    if status.notebook is None:
        # An emptied file holds no code that can produce an entry.
        return set()
    if not status.notebook.valid:
        # Reads as a notebook but holds no app, so its cells are not what
        # running the file executes.
        return None

    try:
        # A cell that does not compile raises here rather than dropping out
        # of the graph, where its absence reads as code that is gone.
        graph = InternalApp(load_notebook_ir(status.notebook)).graph
        return {
            hash_cell_closure(cell_id, graph).hex() for cell_id in graph.cells
        }
    except Exception:
        LOGGER.warning("Could not compile %s", notebook, exc_info=True)
        return None


def _unattested_siblings(cache_dir: Path, keys: Collection[str]) -> list[str]:
    """Notebooks that share `cache_dir` without recording what they put there.

    Their entries are indistinguishable from the dead ones, so a prune that
    deletes anything here needs agreement first.
    """
    notebooks = cache_dir.parent.parent
    if directory_cache_dir(notebooks) != cache_dir:
        return [SIBLINGS_UNVERIFIABLE]
    try:
        children = list(notebooks.iterdir())
    except OSError as e:
        LOGGER.warning("Skipping %s: %s", notebooks, e)
        return [SIBLINGS_UNVERIFIABLE]
    return [
        f"{path.name} shares this cache and has no manifest."
        for path in sorted(children)
        if path.is_file()
        and MarimoPath.is_valid_path(path)
        and manifest_name(path) not in keys
        and is_marimo_notebook(path)
    ]


def _rewrite_manifests(directory: DirectoryPrunePlan) -> None:
    from marimo._save.stores.file import FileStore

    if not directory.rewrites:
        return
    store = FileStore(save_path=str(directory.cache_dir))
    for key, manifest in directory.rewrites:
        try:
            store.put(key, manifest.to_bytes())
        except Exception as e:
            # A record of an entry that is gone reads as a cache miss. A
            # lost manifest turns the directory into one prune never touches.
            LOGGER.warning("Could not rewrite %s: %s", key, e)
