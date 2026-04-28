# Copyright 2026 Marimo. All rights reserved.
"""Merkle hashing over the compilable subgraph.

Each compilable cell gets a content-addressed hash that depends on
the cell's own source plus the hashes of its compilable parents,
sorted to be deterministic. Non-compilable parents are excluded:
their data is materialized inline by the build, so they don't contribute
identity to the resulting artifact.

The hashes drive incremental builds — the artifact filename embeds
the first ~12 hex chars, and re-runs reuse on-disk artifacts whose
hash already matches the recomputed one.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from marimo._save.hash import DEFAULT_HASH, hash_cell_impl

if TYPE_CHECKING:
    from collections.abc import Collection

    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.ids import CellId_t


# Number of hex chars from the digest used in artifact filenames.
HASH_PREFIX_LEN = 12


def compilable_hash(
    cell_id: CellId_t,
    *,
    graph: DirectedGraph,
    compilable: Collection[CellId_t],
    cache: dict[CellId_t, bytes],
) -> bytes:
    """Recursive Merkle hash of ``cell_id`` over the compilable subgraph.

    ``cache`` is required and is mutated in place. Without memoization
    the recursion is exponential in the diamond case (A -> B, A -> C,
    B -> D, C -> D recomputes hash(A) twice for D's children).
    """
    cached = cache.get(cell_id)
    if cached is not None:
        return cached

    parent_hashes = sorted(
        compilable_hash(p, graph=graph, compilable=compilable, cache=cache)
        for p in graph.parents[cell_id]
        if p in compilable
    )

    digest = hashlib.new(DEFAULT_HASH, usedforsecurity=False)
    digest.update(hash_cell_impl(graph.cells[cell_id], DEFAULT_HASH))
    for ph in parent_hashes:
        digest.update(ph)

    result = digest.digest()
    cache[cell_id] = result
    return result


def short_hash(digest: bytes) -> str:
    """Hex-encoded prefix of ``digest`` for use in artifact filenames."""
    return digest.hex()[:HASH_PREFIX_LEN]
