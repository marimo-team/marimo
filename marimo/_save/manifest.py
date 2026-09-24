# Copyright 2026 Marimo. All rights reserved.
"""Record of the cache entries a notebook produced.

A manifest groups cache keys under path hashes. A path hash is a static
digest of a cell and everything it depends on, computed from source alone.
Records accumulate across runs, so an entry stays recorded for as long as
the code that produced it exists, whatever branch or user-interface state
the last run took.

The manifest travels through the same `Store` as the entries it describes,
under a reserved key, so a remote or in-browser cache holds its manifest
too. It is pure and kernel-free, so the CLI can read it without a runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._utils.paths import normalize_path

if TYPE_CHECKING:
    from collections.abc import Collection

    from marimo._runtime.context.types import RuntimeContext
    from marimo._runtime.dataflow.topology import GraphTopology
    from marimo._save.hash import HashKey
    from marimo._save.loaders import Loader
    from marimo._save.stores import Store
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()

MANIFEST_VERSION = 1
MANIFEST_SUFFIX = ".json"
MAX_SLUG_LENGTH = 64
# A manifest ends in a 16-hex path digest, which nothing else at the root of
# a cache directory ends in: a block directory never holds a dot, the export
# manifest ends in `-export.json`, and the leftovers of an interrupted write
# end in their tag.
_MANIFEST_NAME = re.compile(r"[0-9A-Za-z._-]+-[0-9a-f]{16}\.json")


class ManifestError(Exception):
    """Base class for manifest failures."""


class CorruptManifestError(ManifestError):
    """Raised when a manifest cannot be read as one."""


class UnsupportedManifestVersionError(ManifestError):
    """Raised when a manifest comes from a newer version of marimo."""


def manifest_name(notebook_path: str | Path) -> str:
    """Return the reserved store key holding `notebook_path`'s manifest.

    The name carries a digest of the notebook's absolute path, so two
    notebooks that share a cache directory keep separate manifests however
    their stems collide. The stem is kept only to make the file recognizable.
    """
    path = normalize_path(Path(notebook_path))
    slug = re.sub(r"[^0-9A-Za-z._-]+", "-", path.stem).strip("-") or "notebook"
    # The digest tells manifests apart. The stem is only a label, and a long
    # one would push the name past what a filesystem allows.
    slug = slug[:MAX_SLUG_LENGTH]
    # Encoded as the filesystem hands it over: a path that is not valid UTF-8
    # arrives carrying surrogate escapes, which strict encoding rejects.
    digest = hashlib.sha256(
        str(path).encode("utf-8", "surrogateescape")
    ).hexdigest()[:16]
    return f"{slug}-{digest}{MANIFEST_SUFFIX}"


def is_manifest_name(name: str) -> bool:
    """Whether `name` is the reserved key of a cache manifest.

    A cache directory holds other files that describe rather than hold a
    cached value, so recognizing a manifest takes more than the suffix.
    """
    return _MANIFEST_NAME.fullmatch(name) is not None


@dataclass
class CacheManifest:
    """The cache keys a notebook produced, grouped by path hash."""

    # Path to the notebook, relative to the cache directory where possible, so
    # a manifest can be attributed to its notebook after the tree is moved.
    notebook: str = ""
    nodes: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    written_at: str | None = None

    def merge(self, other: CacheManifest) -> None:
        """Union `other`'s keys into this manifest, per path hash and block."""
        for node, blocks in other.nodes.items():
            merged = self.nodes.setdefault(node, {})
            for block, keys in blocks.items():
                merged[block] = merged.get(block, set()) | set(keys)

    def evict_dead(self, live_nodes: Collection[str]) -> set[tuple[str, str]]:
        """Drop the path hashes absent from `live_nodes`.

        Returns the `(block, key)` entries the dropped hashes listed. They
        are only unreachable through this manifest. Another notebook sharing
        the cache directory can still list them.
        """
        live = set(live_nodes)
        evicted: set[tuple[str, str]] = set()
        for node in set(self.nodes) - live:
            for block, keys in self.nodes.pop(node).items():
                evicted.update((block, key) for key in keys)
        return evicted

    def entries(self) -> set[tuple[str, str]]:
        """Every `(block, key)` this manifest attests."""
        return {
            (block, key)
            for blocks in self.nodes.values()
            for block, keys in blocks.items()
            for key in keys
        }

    def to_bytes(self) -> bytes:
        """Serialize to the bytes a store holds under the manifest key."""
        return json.dumps(
            {
                "version": MANIFEST_VERSION,
                "notebook": self.notebook,
                "written_at": self.written_at or _utc_now(),
                "nodes": {
                    node: {
                        block: sorted(keys)
                        for block, keys in sorted(blocks.items())
                    }
                    for node, blocks in sorted(self.nodes.items())
                },
            },
            indent=2,
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> CacheManifest:
        """Parse manifest bytes.

        Raises:
            CorruptManifestError: If `data` is not a manifest.
            UnsupportedManifestVersionError: If it was written by a newer
                marimo, whose semantics this one cannot assume.
        """
        try:
            payload = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise CorruptManifestError(f"Manifest is not JSON: {e}") from e
        if not isinstance(payload, dict):
            raise CorruptManifestError("Manifest is not an object.")

        version = payload.get("version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise CorruptManifestError("Manifest has no version.")
        if version > MANIFEST_VERSION:
            raise UnsupportedManifestVersionError(
                f"Manifest version {version} was written by a newer version "
                f"of marimo; this one reads up to {MANIFEST_VERSION}."
            )

        return cls(
            notebook=_read_str(payload, "notebook"),
            nodes=_read_nodes(payload.get("nodes")),
            written_at=payload.get("written_at")
            if isinstance(payload.get("written_at"), str)
            else None,
        )


def load_manifest(store: Store, key: str) -> CacheManifest | None:
    """Read the manifest `store` holds under `key`, or `None` if it holds none.

    Raises:
        CorruptManifestError: If the stored bytes are not a manifest.
        UnsupportedManifestVersionError: If they come from a newer marimo.
    """
    data = store.get(key)
    if not data:
        return None
    return CacheManifest.from_bytes(data)


def record_cache_event(
    loader: Loader,
    key: HashKey,
    cell_id: CellId_t,
    graph: GraphTopology,
    *,
    saved: bool = False,
) -> None:
    """Record `key` against the cell that defines its cached code.

    `saved` says the entry was just written rather than read. A record
    already made this session is not repeated for a hit, but a write means
    the entry is new on disk, however often it was seen before: something
    else, such as `marimo cache clean`, can have taken the entry and its
    record away in between.

    `cell_id` is the defining cell, which a function cache reaches from
    another cell. The manifest keys on where the cached code is defined, not
    on where it ran. Anything that leaves no on-disk entry to clean up
    records nothing: a session-local cache, a scratchpad cell, a notebook
    with no file.

    Recording happens inside the user's cell, so it reports errors instead
    of raising them. A cache that was written and restored must not fail its
    cell because bookkeeping about it went wrong. The record reaches a store
    when the run finishes.
    """
    try:
        _record_cache_event(loader, key, cell_id, graph, saved=saved)
    except Exception:
        LOGGER.warning("Could not record a cache entry", exc_info=True)


def _record_cache_event(
    loader: Loader,
    key: HashKey,
    cell_id: CellId_t,
    graph: GraphTopology,
    *,
    saved: bool,
) -> None:
    from marimo._runtime.context import safe_get_context
    from marimo._save.loaders import BasePersistenceLoader

    if not isinstance(loader, BasePersistenceLoader):
        return
    if cell_id not in graph.cells:
        return
    ctx = safe_get_context()
    if ctx is None or not ctx.filename:
        return

    from marimo._save.hash import cell_path_hash

    path = loader.build_path(key)
    block, entry = path.parent.name, path.stem
    node = cell_path_hash(cell_id, graph)

    # Records are kept per store. A manifest lists only the entries stored
    # beside it, and a notebook can cache to more than one location.
    store = loader.store
    blocks = ctx.cache.manifest_records.setdefault(store, {}).setdefault(
        node, {}
    )
    keys = blocks.setdefault(block, set())
    if entry in keys and not saved:
        return
    keys.add(entry)
    ctx.cache.manifest_dirty.add(store)


def flush_dirty_manifests(ctx: RuntimeContext) -> None:
    """Write a manifest for every store this session recorded an entry in.

    Writes are coalesced rather than issued per entry. Each write replaces
    the whole manifest, so a per-key flush for a cell that fills a cache
    with a thousand keys rewrites the growing file a thousand times.
    """
    for store in list(ctx.cache.manifest_dirty):
        try:
            written = flush_cache_manifest(ctx, store)
        except Exception:
            LOGGER.warning("Could not write a cache manifest", exc_info=True)
            continue
        if written:
            ctx.cache.manifest_dirty.discard(store)


def flush_cache_manifest(ctx: RuntimeContext, store: Store) -> bool:
    """Merge `store`'s records into its on-disk manifest and write it back.

    Returns whether a manifest was written. A session that produced no
    persistent entry writes nothing, so reading a cache never creates one.
    """
    records = ctx.cache.manifest_records.get(store)
    if not records or not ctx.filename:
        return False

    key = manifest_name(ctx.filename)
    try:
        manifest = load_manifest(store, key) or CacheManifest()
    except UnsupportedManifestVersionError as e:
        # A rewrite under the older schema drops whatever the newer one
        # holds, including the marker that tells a reader to stay away.
        LOGGER.warning("Leaving cache manifest %s alone: %s", key, e)
        ctx.cache.manifest_dirty.discard(store)
        return False
    except ManifestError as e:
        # Bytes that parse as no manifest at all record nothing that can be
        # acted on, so replacing them costs nothing.
        LOGGER.warning("Rewriting unreadable cache manifest %s: %s", key, e)
        manifest = CacheManifest()

    manifest.merge(CacheManifest(nodes=records))
    manifest.notebook = _notebook_ref(ctx.filename, store)
    manifest.written_at = _utc_now()
    try:
        written = store.put(key, manifest.to_bytes())
    except Exception as e:
        LOGGER.warning("Could not write cache manifest %s: %s", key, e)
        return False
    if not written:
        # A store can decline a write by its return value rather than raise.
        LOGGER.warning("Could not write cache manifest %s", key)
    return written


def _notebook_ref(notebook_path: str, store: Store) -> str:
    """Where the manifest records its notebook, relative to the cache dir."""
    path = normalize_path(Path(notebook_path))
    directories = store.local_dirs()
    # A relative reference survives a moved tree, but only reads back as the
    # notebook from the one directory it was measured against. A store that
    # writes the same bytes to several directories has no such directory.
    if len(directories) != 1:
        return path.as_posix()
    try:
        return Path(os.path.relpath(path, directories[0])).as_posix()
    except ValueError:
        # Different Windows drives have no path between them.
        return path.as_posix()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CorruptManifestError(f"Manifest field {field_name} is not text.")
    return value


def _read_nodes(nodes: Any) -> dict[str, dict[str, set[str]]]:
    if nodes is None:
        return {}
    if not isinstance(nodes, dict):
        raise CorruptManifestError("Manifest nodes are not an object.")
    parsed: dict[str, dict[str, set[str]]] = {}
    for node, blocks in nodes.items():
        if not isinstance(node, str) or not isinstance(blocks, dict):
            raise CorruptManifestError("Manifest node is malformed.")
        parsed[node] = {}
        for block, keys in blocks.items():
            if not isinstance(block, str) or not isinstance(keys, list):
                raise CorruptManifestError("Manifest block is malformed.")
            if not all(isinstance(key, str) for key in keys):
                raise CorruptManifestError("Manifest key is not text.")
            parsed[node][block] = set(keys)
    return parsed
