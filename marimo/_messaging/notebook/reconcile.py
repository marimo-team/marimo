# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from typing import TYPE_CHECKING

from msgspec.structs import replace as structs_replace

from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    MoveCell,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
)
from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    from marimo._messaging.notebook.changes import DocumentChange
    from marimo._messaging.notebook.document import NotebookDocument
    from marimo._types.ids import CellId_t


def reconcile_transaction(
    changes: tuple[DocumentChange, ...],
    document: NotebookDocument,
) -> tuple[DocumentChange, ...]:
    """Rewrite `changes` so they apply cleanly to `document`.

    Resolves references in batch order against a shadow id-set seeded from
    the document and mutated per change, so a cell created earlier in the
    same batch satisfies a later anchor. A create with an unresolvable anchor
    is appended (its anchor stripped); a create whose id is already taken is
    dropped. Property updates targeting a missing cell, and moves that target
    a missing cell or lack a single resolvable anchor, are dropped.
    """
    # current cells in the document model
    live: set[CellId_t] = set(document.cell_ids)
    # ids a create can't reuse; grows but never shrinks, mirroring
    # `_validate` which never frees an id within a transaction
    claimed: set[CellId_t] = set(document.cell_ids)
    out: list[DocumentChange] = []

    # an anchor resolves when it is a live cell, or None (meaning no anchor)
    def resolve_anchor(anchor: CellId_t | None) -> bool:
        return anchor is None or anchor in live

    for change in changes:
        if isinstance(change, CreateCell):
            if change.cell_id in claimed:
                continue
            # if no anchor cell exists, just append the new cell
            if not resolve_anchor(change.after) or not resolve_anchor(
                change.before
            ):
                change = structs_replace(change, after=None, before=None)
            live.add(change.cell_id)
            claimed.add(change.cell_id)
            out.append(change)
        elif isinstance(change, DeleteCell):
            if change.cell_id not in live:
                continue
            # track removal
            live.discard(change.cell_id)
            out.append(change)
        elif isinstance(change, MoveCell):
            if change.cell_id not in live:
                continue
            # no anchor, or a self-anchor, has no valid destination
            if change.after is None and change.before is None:
                continue
            if change.cell_id in (change.after, change.before):
                continue
            if not resolve_anchor(change.after) or not resolve_anchor(
                change.before
            ):
                continue
            out.append(change)
        elif isinstance(change, (SetCode, SetName, SetConfig)):
            # if cell is missing, skip
            if change.cell_id not in live:
                continue
            out.append(change)
        elif isinstance(change, ReorderCells):
            # already handles unknown/missing ids
            out.append(change)
        else:
            assert_never(change)

    return tuple(out)
