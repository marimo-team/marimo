# Copyright 2026 Marimo. All rights reserved.
"""Internal operation types, plan builder, and validation for code mode."""

from __future__ import annotations

from dataclasses import dataclass

from marimo._ast.cell import CellConfig
from marimo._types.ids import CellId_t

# ------------------------------------------------------------------
# Operation types (queued by mutation methods)
# ------------------------------------------------------------------


@dataclass(frozen=True)
class _AddOp:
    cell_id: CellId_t
    code: str
    config: CellConfig
    draft: bool = False
    before: CellId_t | None = None
    after: CellId_t | None = None
    name: str | None = None


@dataclass(frozen=True)
class _UpdateOp:
    cell_id: CellId_t
    code: str | None = None
    config: CellConfig | None = None
    draft: bool = False
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
    draft: bool = False
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
                draft=op.draft,
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
            entry.draft = op.draft

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


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


def _validate_ops(ops: list[_Op]) -> None:
    """Check for conflicting operations. Raises ``ValueError`` on conflict."""
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
