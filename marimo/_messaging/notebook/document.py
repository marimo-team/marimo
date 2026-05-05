# Copyright 2026 Marimo. All rights reserved.
"""Canonical notebook document model.

``NotebookDocument`` maintains an ordered list of ``NotebookCell`` entries and
applies ``Transaction``s atomically.  It is a pure state machine — no IO, no
notifications, no kernel interaction.

Concurrency model
-----------------
The session holds the single ``NotebookDocument`` and applies
transactions sequentially. There is no concurrent access.  Everything
that goes through this model is last-write-wins with intra-transaction
conflict detection (``_validate`` catches contradictions like delete +
update on the same cell within one batch).

``SetCode`` is a wholesale replacement without character-level
merge. Loro CRDT may handle real-time collaborative text editing in
the future, but cell code would then live outside this model entirely.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Iterator

import msgspec
from msgspec.structs import replace as structs_replace

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    DocumentChange,
    MoveCell,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
)
from marimo._types.ids import CellId_t


class NotebookCell(msgspec.Struct):
    """A single cell in the document. Mutable — owned by the document."""

    id: CellId_t
    code: str
    name: str
    config: CellConfig

    def __repr__(self) -> str:
        first_line = self.code.split("\n", 1)[0]
        if len(first_line) > 80:
            code_preview = first_line[:80] + "..."
        elif "\n" in self.code:
            code_preview = first_line + "..."
        else:
            code_preview = first_line
        name_part = f", name={self.name!r}" if self.name else ""
        return (
            f"NotebookCell(id={self.id!r}{name_part}, code={code_preview!r})"
        )


class NotebookDocument:
    """Ordered collection of cells with transactional updates.

    Usage::

        doc = NotebookDocument(
            [
                NotebookCell(CellId_t("a"), "x = 1", "__", CellConfig()),
            ]
        )
        tx = Transaction(
            changes=(SetCode(CellId_t("a"), "x = 2"),), source="kernel"
        )
        applied = doc.apply(tx)
        assert applied.version == 1
        assert doc.get_cell(CellId_t("a")).code == "x = 2"
    """

    def __init__(self, cells: Iterable[NotebookCell] | None = None) -> None:
        self._cells: list[NotebookCell] = list(cells) if cells else []
        self._version: int = 0

    # ------------------------------------------------------------------
    # Read-only accessors
    # ------------------------------------------------------------------

    @property
    def cells(self) -> list[NotebookCell]:
        """Return a shallow copy of the cell list."""
        return list(self._cells)

    @property
    def cell_ids(self) -> list[CellId_t]:
        """Cell IDs in document order."""
        return [c.id for c in self._cells]

    @property
    def version(self) -> int:
        return self._version

    def get_cell(self, cell_id: CellId_t) -> NotebookCell:
        """Lookup by ID. Raises ``KeyError`` if not found."""
        for cell in self._cells:
            if cell.id == cell_id:
                return cell
        raise KeyError(f"Cell {cell_id!r} not found in document")

    def get(self, cell_id: CellId_t) -> NotebookCell | None:
        """Lookup by ID, returning ``None`` if not found."""
        for cell in self._cells:
            if cell.id == cell_id:
                return cell
        return None

    def __contains__(self, cell_id: object) -> bool:
        return any(c.id == cell_id for c in self._cells)

    def __len__(self) -> int:
        return len(self._cells)

    def __iter__(self) -> Iterator[CellId_t]:
        return (c.id for c in self._cells)

    # ------------------------------------------------------------------
    # Transaction application
    # ------------------------------------------------------------------

    def apply(self, tx: Transaction) -> Transaction:
        """Validate and apply *tx*, return it with ``version`` assigned.

        Raises ``ValueError`` for validation failures and ``KeyError``
        when a change references a non-existent cell.
        """
        if not tx.changes:
            return structs_replace(tx, version=self._version)

        _validate(tx.changes, self._cells)

        for change in tx.changes:
            self._apply_change(change)

        self._version += 1
        return structs_replace(tx, version=self._version)

    def _apply_change(self, change: DocumentChange) -> None:
        # TODO: refactor to use match/case (min Python is 3.10) once
        # ruff target-version is bumped from py39.
        if isinstance(change, CreateCell):
            cell = NotebookCell(
                id=change.cell_id,
                code=change.code,
                name=change.name,
                config=change.config,
            )
            if change.after is not None:
                idx = self._find_index(change.after)
                self._cells.insert(idx + 1, cell)
            elif change.before is not None:
                idx = self._find_index(change.before)
                self._cells.insert(idx, cell)
            else:
                self._cells.append(cell)

        elif isinstance(change, DeleteCell):
            idx = self._find_index(change.cell_id)
            del self._cells[idx]

        elif isinstance(change, MoveCell):
            idx = self._find_index(change.cell_id)
            cell = self._cells.pop(idx)
            if change.after is not None:
                target = self._find_index(change.after)
                self._cells.insert(target + 1, cell)
            elif change.before is not None:
                target = self._find_index(change.before)
                self._cells.insert(target, cell)
            else:
                raise ValueError("MoveCell requires 'before' or 'after'")

        elif isinstance(change, ReorderCells):
            by_id = {c.id: c for c in self._cells}
            seen: set[CellId_t] = set()
            reordered: list[NotebookCell] = []
            for cid in change.cell_ids:
                if cid in by_id and cid not in seen:
                    reordered.append(by_id[cid])
                    seen.add(cid)
            # Append any cells not mentioned in the new ordering.
            for c in self._cells:
                if c.id not in seen:
                    reordered.append(c)
            self._cells = reordered

        elif isinstance(change, SetCode):
            self._find_cell(change.cell_id).code = change.code

        elif isinstance(change, SetName):
            self._find_cell(change.cell_id).name = change.name

        elif isinstance(change, SetConfig):
            cell = self._find_cell(change.cell_id)
            cell.config = CellConfig(
                column=change.column,
                disabled=change.disabled,
                hide_code=change.hide_code,
            )
        else:
            assert_never(change)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _replace_cells(self, cells: list[NotebookCell]) -> None:
        """Bulk-replace the cell list in place, bypassing ``apply``.

        Transitional. Used for full-document rebuilds (save round-trip)
        until those flows are expressed as diff Transactions. The
        ``_cells`` attribute is reassigned (not mutated element-wise)
        so any external holder of the prior list keeps a snapshot of
        pre-rebuild state — useful for diff comparison. Bumps
        ``version`` so observers see the state change like they would
        after ``apply()``.
        """
        self._cells = cells
        self._version += 1

    def _rekey(self, mapping: dict[CellId_t, CellId_t]) -> None:
        """Rekey cells by an old-id to new-id mapping, preserving order.

        Cells whose id is not in ``mapping`` keep their existing id.
        Each rekeyed cell is replaced by a fresh ``NotebookCell`` so its
        primary key is stable from construction to disposal. Bumps
        ``version`` so observers see the rekey as a state change.

        Raises ``ValueError`` if the rekey would produce duplicate ids.
        """
        final_ids: set[CellId_t] = set()
        for c in self._cells:
            new_id = mapping.get(c.id, c.id)
            if new_id in final_ids:
                raise ValueError(
                    f"Rekey would produce duplicate cell id {new_id!r}"
                )
            final_ids.add(new_id)

        self._cells = [
            structs_replace(c, id=mapping[c.id]) if c.id in mapping else c
            for c in self._cells
        ]
        self._version += 1

    def _find_index(self, cell_id: CellId_t) -> int:
        for i, cell in enumerate(self._cells):
            if cell.id == cell_id:
                return i
        raise KeyError(f"Cell {cell_id!r} not found in document")

    def _find_cell(self, cell_id: CellId_t) -> NotebookCell:
        for cell in self._cells:
            if cell.id == cell_id:
                return cell
        raise KeyError(f"Cell {cell_id!r} not found in document")

    def __repr__(self) -> str:
        lines = [f"NotebookDocument({len(self._cells)} cells):"]
        for i, c in enumerate(self._cells):
            code_preview = c.code[:40].replace("\n", "\\n")
            lines.append(f"  {i}: {c.id} {code_preview!r}")
        return "\n".join(lines)


# ------------------------------------------------------------------
# Context variable
# ------------------------------------------------------------------

#: Document snapshot for the current scratchpad execution. Set by the
#: kernel before running code_mode so ``AsyncCodeModeContext`` can read
#: cell ordering, code, names, and configs without the kernel carrying
#: mutable document state.
_current_document: ContextVar[NotebookDocument | None] = ContextVar(
    "_current_document", default=None
)


def get_current_document() -> NotebookDocument | None:
    """Return the document for the current execution, if any."""
    return _current_document.get()


@contextmanager
def notebook_document_context(
    doc: NotebookDocument | None,
) -> Generator[None, None, None]:
    """Context manager for setting and resetting the current document."""
    token = _current_document.set(doc)
    try:
        yield
    finally:
        _current_document.reset(token)


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


def _validate(
    changes: tuple[DocumentChange, ...], cells: list[NotebookCell]
) -> None:
    """Check for conflicting changes. Raises ``ValueError``."""
    existing_ids = {c.id for c in cells}
    created: set[CellId_t] = set()
    deleted: set[CellId_t] = set()
    updated: set[CellId_t] = set()
    moved: set[CellId_t] = set()

    for change in changes:
        if isinstance(change, CreateCell):
            if change.cell_id in existing_ids or change.cell_id in created:
                raise ValueError(f"Cell {change.cell_id!r} already exists")
            if change.before is not None and change.after is not None:
                raise ValueError(
                    "CreateCell cannot specify both 'before' and 'after'"
                )
            created.add(change.cell_id)

        elif isinstance(change, DeleteCell):
            if change.cell_id in deleted:
                raise ValueError(
                    f"Cell {change.cell_id!r} is deleted more than once"
                )
            if change.cell_id in updated:
                raise ValueError(
                    f"Cannot delete cell {change.cell_id!r} that is also "
                    f"updated in the same transaction"
                )
            if change.cell_id in moved:
                raise ValueError(
                    f"Cannot delete cell {change.cell_id!r} that is also "
                    f"moved in the same transaction"
                )
            deleted.add(change.cell_id)

        elif isinstance(change, MoveCell):
            if change.cell_id in deleted:
                raise ValueError(
                    f"Cannot move cell {change.cell_id!r} that is also "
                    f"deleted in the same transaction"
                )
            if change.before is not None and change.after is not None:
                raise ValueError(
                    "MoveCell cannot specify both 'before' and 'after'"
                )
            if change.before is None and change.after is None:
                raise ValueError("MoveCell requires 'before' or 'after'")
            moved.add(change.cell_id)

        elif isinstance(change, ReorderCells):
            pass  # No conflicts — replaces full ordering

        elif isinstance(change, (SetCode, SetName, SetConfig)):
            if change.cell_id in deleted:
                raise ValueError(
                    f"Cannot update cell {change.cell_id!r} that is also "
                    f"deleted in the same transaction"
                )
            updated.add(change.cell_id)

        else:
            raise TypeError(f"Unknown change type: {type(change)!r}")
