# Copyright 2026 Marimo. All rights reserved.
"""Internal operation types, plan builder, and validation for code mode."""

from __future__ import annotations

from dataclasses import dataclass

from marimo._ast.cell import CellConfig
from marimo._core import protocol
from marimo._core.document import Document, DocumentCell
from marimo._messaging.host import document_config
from marimo._types.ids import CellId_t

# ------------------------------------------------------------------
# Operation types (queued by mutation methods)
# ------------------------------------------------------------------


@dataclass(frozen=True)
class _AddOp:
    cell_id: CellId_t
    code: str
    config: CellConfig
    before: CellId_t | None = None
    after: CellId_t | None = None
    name: str | None = None


@dataclass(frozen=True)
class _UpdateOp:
    cell_id: CellId_t
    code: str | None = None
    config: CellConfig | None = None
    name: str | None = None
    new_cell_id: CellId_t | None = None


@dataclass(frozen=True)
class _DeleteOp:
    cell_id: CellId_t


@dataclass(frozen=True)
class _MoveOp:
    cell_id: CellId_t
    before: CellId_t | None = None
    after: CellId_t | None = None


_Op = _AddOp | _UpdateOp | _DeleteOp | _MoveOp


# ------------------------------------------------------------------
# Plan entry
# ------------------------------------------------------------------


@dataclass
class _PlanEntry:
    cell_id: CellId_t
    code: str | None = None
    config: CellConfig | None = None
    name: str | None = None


# ------------------------------------------------------------------
# Plan builder
# ------------------------------------------------------------------


def _build_plan(
    existing_cell_ids: list[CellId_t],
    ops: list[_Op],
) -> list[_PlanEntry]:
    """Reduce a list of queued operations into a flat plan.

    Pure function. The returned plan describes the target cell list
    after all operations are applied sequentially.
    """
    plan: list[_PlanEntry] = [
        _PlanEntry(cell_id=cid) for cid in existing_cell_ids
    ]

    def _find_index(cell_id: CellId_t) -> int:
        for i, entry in enumerate(plan):
            if entry.cell_id == cell_id:
                return i
        raise KeyError(f"Cell {cell_id!r} not found in plan")

    for op in ops:
        if isinstance(op, _AddOp):
            entry = _PlanEntry(
                cell_id=op.cell_id,
                code=op.code,
                config=op.config,
                name=op.name,
            )
            if op.after is not None:
                idx = _find_index(op.after)
                plan.insert(idx + 1, entry)
            elif op.before is not None:
                idx = _find_index(op.before)
                plan.insert(idx, entry)
            else:
                # Default: append at end
                plan.append(entry)

        elif isinstance(op, _UpdateOp):
            idx = _find_index(op.cell_id)
            entry = plan[idx]
            if op.new_cell_id is not None:
                entry.cell_id = op.new_cell_id
            if op.code is not None:
                entry.code = op.code
            if op.config is not None:
                entry.config = op.config
            if op.name is not None:
                entry.name = op.name

        elif isinstance(op, _DeleteOp):
            idx = _find_index(op.cell_id)
            del plan[idx]

        elif isinstance(op, _MoveOp):
            idx = _find_index(op.cell_id)
            entry = plan.pop(idx)
            if op.after is not None:
                target_idx = _find_index(op.after)
                plan.insert(target_idx + 1, entry)
            elif op.before is not None:
                target_idx = _find_index(op.before)
                plan.insert(target_idx, entry)
            else:
                raise ValueError("move_cell requires before or after")

        else:
            raise TypeError(f"Unknown op type: {type(op)!r}")

    return plan


def _document_changes(
    document: Document, plan: list[_PlanEntry]
) -> list[protocol.Change]:
    """Describe a resolved plan using the revisions it was prepared against."""
    cells: list[DocumentCell] = []
    for entry in plan:
        cell_id = protocol.CellId(entry.cell_id)
        previous = document.cell(cell_id)
        if previous is None:
            if entry.code is None:
                raise ValueError(f"New cell {cell_id!r} requires source")
            code, name = entry.code, ""
            config = protocol.CellConfig(
                column=None,
                disabled=False,
                hide_code=True,
                expand_output=False,
            )
        else:
            code, name, config = previous.code, previous.name, previous.config
        if entry.config is not None:
            config = document_config(entry.config)
        cells.append(
            DocumentCell(
                cell_id,
                code if entry.code is None else entry.code,
                name if entry.name is None else entry.name,
                config,
            )
        )

    target, changed = document.replace(cells, document.app_config)
    changes: list[protocol.Change] = []
    for cell in document:
        if target.cell(cell.id) is None:
            changes.append(
                protocol.DeleteCell(id=cell.id, base_etag=cell.etag)
            )
    for cell in changed.cells:
        previous = document.cell(cell.id)
        changes.append(
            protocol.PutCell(
                base_etag=None if previous is None else previous.etag,
                cell=protocol.CellInput(
                    id=cell.id,
                    code=cell.code,
                    name=cell.name,
                    config=protocol.CellConfigInput(
                        column=cell.config.column,
                        disabled=cell.config.disabled,
                        hide_code=cell.config.hide_code,
                        expand_output=cell.config.expand_output,
                    ),
                ),
            )
        )
    wanted = [cell.id for cell in target]
    if [cell.id for cell in document] != wanted:
        changes.append(
            protocol.SetOrder(
                base_etag=document.order_etag, order=tuple(wanted)
            )
        )
    return changes


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


def _validate_ops(ops: list[_Op]) -> None:
    """Check for conflicting operations. Raises `ValueError` on conflict."""
    deleted: set[CellId_t] = set()
    updated: set[CellId_t] = set()
    moved: set[CellId_t] = set()

    for op in ops:
        if isinstance(op, _DeleteOp):
            if op.cell_id in updated:
                raise ValueError(
                    f"Cannot delete cell {op.cell_id!r} that is also "
                    f"updated in the same batch"
                )
            if op.cell_id in moved:
                raise ValueError(
                    f"Cannot delete cell {op.cell_id!r} that is also "
                    f"moved in the same batch"
                )
            if op.cell_id in deleted:
                raise ValueError(
                    f"Cell {op.cell_id!r} is deleted more than once"
                )
            deleted.add(op.cell_id)

        elif isinstance(op, _UpdateOp):
            if op.cell_id in deleted:
                raise ValueError(
                    f"Cannot update cell {op.cell_id!r} that is also "
                    f"deleted in the same batch"
                )
            updated.add(op.cell_id)

        elif isinstance(op, _MoveOp):
            if op.cell_id in deleted:
                raise ValueError(
                    f"Cannot move cell {op.cell_id!r} that is also "
                    f"deleted in the same batch"
                )
            moved.add(op.cell_id)
