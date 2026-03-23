# Copyright 2026 Marimo. All rights reserved.
"""Notebook document model.

The single source of truth for notebook structure. Both the frontend
and the kernel emit events that mutate this document. The document
is the canonical ordered list of cells — their IDs, code, names,
and configs.

Execution is a separate concern. The kernel reads from the document
to know *what* code a cell contains; the dependency graph determines
*when* it runs. Cell ordering in the document is purely visual.

Conflict resolution is last-write-wins. Events are applied in the
order they arrive. There is no merging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Union

import msgspec

from marimo._ast.cell import CellConfig
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._ast.cell_manager import CellManager


# ------------------------------------------------------------------
# Notebook cell
# ------------------------------------------------------------------


class NotebookCell(msgspec.Struct):
    """A cell in the notebook document."""

    id: CellId_t
    code: str
    name: str = ""
    config: CellConfig = msgspec.field(default_factory=CellConfig)


# ------------------------------------------------------------------
# Events
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CellCreated:
    """A new cell was added to the notebook."""

    id: CellId_t
    code: str
    name: str = ""
    config: CellConfig = field(default_factory=CellConfig)
    after: CellId_t | None = None


@dataclass(frozen=True, slots=True)
class CellDeleted:
    """A cell was removed from the notebook."""

    id: CellId_t


@dataclass(frozen=True, slots=True)
class CellMoved:
    """A cell was moved to a new position.

    ``after=None`` means move to the very beginning.
    """

    id: CellId_t
    after: CellId_t | None = None


@dataclass(frozen=True, slots=True)
class CellsReordered:
    """Full cell ordering was set.

    Replaces the entire cell order. Cell IDs that exist in the document
    but not in the list are left in place at the end. IDs not in the
    document are ignored.
    """

    cell_ids: list[CellId_t]


@dataclass(frozen=True, slots=True)
class CodeChanged:
    """A cell's code was changed (but not yet executed)."""

    id: CellId_t
    code: str


@dataclass(frozen=True, slots=True)
class NameChanged:
    """A cell was renamed."""

    id: CellId_t
    name: str


@dataclass(frozen=True, slots=True)
class ConfigChanged:
    """A cell's configuration was changed."""

    id: CellId_t
    config: CellConfig


DocumentEvent = Union[
    CellCreated,
    CellDeleted,
    CellMoved,
    CellsReordered,
    CodeChanged,
    NameChanged,
    ConfigChanged,
]


# ------------------------------------------------------------------
# Document
# ------------------------------------------------------------------


class NotebookDocument:
    """Ordered list of notebook cells.

    This is the materialized view of the event log. Both the frontend
    and the kernel write events to it; it is the single source of truth
    for document structure.
    """

    __slots__ = ("_cells", "_index")

    def __init__(self, cells: list[NotebookCell] | None = None) -> None:
        self._cells: list[NotebookCell] = list(cells) if cells else []
        self._index: dict[CellId_t, int] = {
            c.id: i for i, c in enumerate(self._cells)
        }

    @classmethod
    def from_cell_manager(cls, cell_manager: CellManager) -> NotebookDocument:
        """Build a document from a CellManager's current state."""
        cells = [
            NotebookCell(
                id=cd.cell_id,
                code=cd.code,
                name=cd.name,
                config=cd.config,
            )
            for cd in cell_manager.cell_data()
        ]
        return cls(cells)

    # -- Mapping-style reads ----------------------------------------
    #
    # Iteration order is notebook order.  ``list(doc)`` gives cell IDs,
    # ``list(doc.values())`` gives cells, ``doc[cell_id]`` looks up by
    # ID (KeyError if missing), ``doc.get(cell_id)`` returns None.

    def __getitem__(self, cell_id: CellId_t) -> NotebookCell:
        return self._cells[self._require_index(cell_id)]

    def get(self, cell_id: CellId_t) -> NotebookCell | None:
        idx = self._index.get(cell_id)
        return self._cells[idx] if idx is not None else None

    def __iter__(self) -> Iterator[CellId_t]:
        return (c.id for c in self._cells)

    def values(self) -> Iterator[NotebookCell]:
        """Iterate over cells in notebook order."""
        return iter(self._cells)

    def __len__(self) -> int:
        return len(self._cells)

    def __contains__(self, cell_id: object) -> bool:
        return cell_id in self._index

    # -- Mutation ---------------------------------------------------

    def apply(self, event: DocumentEvent) -> None:
        """Apply a single event to the document. Mutates in place.

        Raises ``KeyError`` if the event references a cell that does
        not exist, or ``ValueError`` if the event is invalid (e.g.
        creating a cell with a duplicate ID).
        """
        if isinstance(event, CellCreated):
            self._apply_created(event)
        elif isinstance(event, CellDeleted):
            self._apply_deleted(event)
        elif isinstance(event, CellMoved):
            self._apply_moved(event)
        elif isinstance(event, CellsReordered):
            self._apply_reordered(event)
        elif isinstance(event, CodeChanged):
            self._apply_code_changed(event)
        elif isinstance(event, NameChanged):
            self._apply_name_changed(event)
        elif isinstance(event, ConfigChanged):
            self._apply_config_changed(event)
        else:
            raise TypeError(f"Unknown event type: {type(event)!r}")

    # -- Private ----------------------------------------------------

    def _require_index(self, cell_id: CellId_t) -> int:
        try:
            return self._index[cell_id]
        except KeyError:
            raise KeyError(f"Cell {cell_id!r} not in document") from None

    def _rebuild_index(self) -> None:
        self._index = {c.id: i for i, c in enumerate(self._cells)}

    def _insert_at(self, cell: NotebookCell, after: CellId_t | None) -> None:
        if after is None:
            self._cells.append(cell)
        else:
            idx = self._require_index(after)
            self._cells.insert(idx + 1, cell)
        self._rebuild_index()

    def _apply_created(self, event: CellCreated) -> None:
        if event.id in self._index:
            raise ValueError(f"Cell {event.id!r} already exists in document")
        cell = NotebookCell(
            id=event.id,
            code=event.code,
            name=event.name,
            config=event.config,
        )
        self._insert_at(cell, event.after)

    def _apply_deleted(self, event: CellDeleted) -> None:
        idx = self._require_index(event.id)
        del self._cells[idx]
        self._rebuild_index()

    def _apply_moved(self, event: CellMoved) -> None:
        idx = self._require_index(event.id)
        cell = self._cells.pop(idx)
        self._rebuild_index()
        if event.after is None:
            self._cells.insert(0, cell)
        else:
            after_idx = self._require_index(event.after)
            self._cells.insert(after_idx + 1, cell)
        self._rebuild_index()

    def _apply_reordered(self, event: CellsReordered) -> None:
        by_id = {c.id: c for c in self._cells}
        seen: set[CellId_t] = set()
        reordered: list[NotebookCell] = []
        for cid in event.cell_ids:
            if cid in by_id and cid not in seen:
                reordered.append(by_id[cid])
                seen.add(cid)
        # Append any cells not in the new ordering.
        for c in self._cells:
            if c.id not in seen:
                reordered.append(c)
        self._cells = reordered
        self._rebuild_index()

    def _apply_code_changed(self, event: CodeChanged) -> None:
        cell = self._cells[self._require_index(event.id)]
        cell.code = event.code

    def _apply_name_changed(self, event: NameChanged) -> None:
        cell = self._cells[self._require_index(event.id)]
        cell.name = event.name

    def _apply_config_changed(self, event: ConfigChanged) -> None:
        cell = self._cells[self._require_index(event.id)]
        cell.config = event.config

    # -- Display ----------------------------------------------------

    def __repr__(self) -> str:
        lines = [f"NotebookDocument({len(self._cells)} cells):"]
        for i, c in enumerate(self._cells):
            code_preview = c.code[:40].replace("\n", "\\n")
            lines.append(f"  {i}: {c.id} {code_preview!r}")
        return "\n".join(lines)
