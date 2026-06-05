# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    DocumentChange,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
    TransactionSource,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._ast.cell_manager import CellManager


def build_transaction(
    *, prev: CellManager, new: CellManager, source: TransactionSource
) -> tuple[Transaction, set[CellId_t]]:
    """Diff two CellManagers, returning `(transaction, changed_cell_ids)`.

    The transaction is unstamped; the caller applies it to the document
    (which assigns `version`). `changed_cell_ids` covers code, name,
    or config changes plus all creates and deletes - reorder-only cells
    are excluded.
    """
    prev_data = {cd.cell_id: cd for cd in prev.cell_data()}
    prev_cell_ids = list(prev.cell_ids())
    new_cell_ids = list(new.cell_ids())
    deleted = set(prev_data) - set(new_cell_ids)

    changes: list[DocumentChange] = []
    changed_cell_ids: set[CellId_t] = set(deleted)
    for cid in deleted:
        changes.append(DeleteCell(cell_id=cid))

    for cd in new.cell_data():
        prev_cd = prev_data.get(cd.cell_id)
        if prev_cd is None:
            changes.append(
                CreateCell(
                    cell_id=cd.cell_id,
                    code=cd.code,
                    name=cd.name,
                    config=cd.config,
                )
            )
            changed_cell_ids.add(cd.cell_id)
            continue
        if cd.code != prev_cd.code:
            changes.append(SetCode(cell_id=cd.cell_id, code=cd.code))
            changed_cell_ids.add(cd.cell_id)
        if cd.name != prev_cd.name:
            changes.append(SetName(cell_id=cd.cell_id, name=cd.name))
            changed_cell_ids.add(cd.cell_id)
        if cd.config != prev_cd.config:
            changes.append(
                SetConfig(
                    cell_id=cd.cell_id,
                    column=cd.config.column,
                    disabled=cd.config.disabled,
                    hide_code=cd.config.hide_code,
                )
            )
            changed_cell_ids.add(cd.cell_id)

    if tuple(new_cell_ids) != tuple(prev_cell_ids):
        changes.append(ReorderCells(cell_ids=tuple(new_cell_ids)))

    return (
        Transaction(changes=tuple(changes), source=source),
        changed_cell_ids,
    )
