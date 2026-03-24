# Copyright 2026 Marimo. All rights reserved.
"""Canonical notebook document model.

``NotebookDocument`` maintains an ordered list of ``NotebookCell`` entries and
applies ``Transaction``s atomically.  It is a pure state machine — no IO, no
notifications, no kernel interaction.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

import msgspec
from msgspec.structs import replace as structs_replace

from marimo._ast.cell import CellConfig
from marimo._notebook.ops import (
    CreateCell,
    DeleteCell,
    MoveCell,
    Op,
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


class NotebookDocument:
    """Ordered collection of cells with transactional updates.

    Usage::

        doc = NotebookDocument(
            [
                NotebookCell(CellId_t("a"), "x = 1", "__", CellConfig()),
            ]
        )
        tx = Transaction(
            ops=(SetCode(CellId_t("a"), "x = 2"),), source="kernel"
        )
        applied = doc.apply(tx)
        assert applied.version == 1
        assert doc.get_cell(CellId_t("a")).code == "x = 2"
    """

    def __init__(self, cells: Optional[Iterable[NotebookCell]] = None) -> None:
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
        when an op references a non-existent cell.
        """
        if not tx.ops:
            return structs_replace(tx, version=self._version)

        _validate(tx.ops, self._cells)

        for op in tx.ops:
            self._apply_op(op)

        self._version += 1
        return structs_replace(tx, version=self._version)

    def _apply_op(self, op: Op) -> None:
        if isinstance(op, CreateCell):
            cell = NotebookCell(
                id=op.cell_id,
                code=op.code,
                name=op.name,
                config=op.config,
            )
            if op.after is not None:
                idx = self._find_index(op.after)
                self._cells.insert(idx + 1, cell)
            elif op.before is not None:
                idx = self._find_index(op.before)
                self._cells.insert(idx, cell)
            else:
                self._cells.append(cell)

        elif isinstance(op, DeleteCell):
            idx = self._find_index(op.cell_id)
            del self._cells[idx]

        elif isinstance(op, MoveCell):
            idx = self._find_index(op.cell_id)
            cell = self._cells.pop(idx)
            if op.after is not None:
                target = self._find_index(op.after)
                self._cells.insert(target + 1, cell)
            elif op.before is not None:
                target = self._find_index(op.before)
                self._cells.insert(target, cell)
            else:
                raise ValueError("MoveCell requires 'before' or 'after'")

        elif isinstance(op, ReorderCells):
            by_id = {c.id: c for c in self._cells}
            seen: set[CellId_t] = set()
            reordered: list[NotebookCell] = []
            for cid in op.cell_ids:
                if cid in by_id and cid not in seen:
                    reordered.append(by_id[cid])
                    seen.add(cid)
            # Append any cells not mentioned in the new ordering.
            for c in self._cells:
                if c.id not in seen:
                    reordered.append(c)
            self._cells = reordered

        elif isinstance(op, SetCode):
            self._find_cell(op.cell_id).code = op.code

        elif isinstance(op, SetName):
            self._find_cell(op.cell_id).name = op.name

        elif isinstance(op, SetConfig):
            cell = self._find_cell(op.cell_id)
            cell.config = CellConfig(
                column=op.column
                if op.column is not None
                else cell.config.column,
                disabled=op.disabled
                if op.disabled is not None
                else cell.config.disabled,
                hide_code=op.hide_code
                if op.hide_code is not None
                else cell.config.hide_code,
            )
        else:
            raise TypeError(f"Unknown op type: {type(op)!r}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


def _validate(ops: tuple[Op, ...], cells: list[NotebookCell]) -> None:
    """Check for conflicting operations. Raises ``ValueError``."""
    existing_ids = {c.id for c in cells}
    created: set[CellId_t] = set()
    deleted: set[CellId_t] = set()
    updated: set[CellId_t] = set()
    moved: set[CellId_t] = set()

    for op in ops:
        if isinstance(op, CreateCell):
            if op.cell_id in existing_ids or op.cell_id in created:
                raise ValueError(f"Cell {op.cell_id!r} already exists")
            if op.before is not None and op.after is not None:
                raise ValueError(
                    "CreateCell cannot specify both 'before' and 'after'"
                )
            created.add(op.cell_id)

        elif isinstance(op, DeleteCell):
            if op.cell_id in deleted:
                raise ValueError(
                    f"Cell {op.cell_id!r} is deleted more than once"
                )
            if op.cell_id in updated:
                raise ValueError(
                    f"Cannot delete cell {op.cell_id!r} that is also "
                    f"updated in the same transaction"
                )
            if op.cell_id in moved:
                raise ValueError(
                    f"Cannot delete cell {op.cell_id!r} that is also "
                    f"moved in the same transaction"
                )
            deleted.add(op.cell_id)

        elif isinstance(op, MoveCell):
            if op.cell_id in deleted:
                raise ValueError(
                    f"Cannot move cell {op.cell_id!r} that is also "
                    f"deleted in the same transaction"
                )
            if op.before is not None and op.after is not None:
                raise ValueError(
                    "MoveCell cannot specify both 'before' and 'after'"
                )
            if op.before is None and op.after is None:
                raise ValueError("MoveCell requires 'before' or 'after'")
            moved.add(op.cell_id)

        elif isinstance(op, ReorderCells):
            pass  # No conflicts — replaces full ordering

        elif isinstance(op, (SetCode, SetName, SetConfig)):
            if op.cell_id in deleted:
                raise ValueError(
                    f"Cannot update cell {op.cell_id!r} that is also "
                    f"deleted in the same transaction"
                )
            updated.add(op.cell_id)

        else:
            raise TypeError(f"Unknown op type: {type(op)!r}")
