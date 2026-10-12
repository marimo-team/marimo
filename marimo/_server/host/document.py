# Copyright 2026 Marimo. All rights reserved.
"""Translate between host records and the editor's document model.

The host owns protocol edits and etags. Sessions still own the editor's
transaction history. Forward host edits as one session transaction;
mirroring the resulting notification back into the host is a no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._core import protocol
from marimo._core.document import CellSource
from marimo._messaging.notebook import (
    CreateCell,
    DeleteCell,
    DocumentChange,
    NotebookCell,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
)
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._core.document import Document
    from marimo._session.notebook import AppFileManager
    from marimo._session.session import Session


def from_session(session: Session) -> tuple[list[CellSource], dict[str, Any]]:
    cells = [
        CellSource(
            protocol.CellId(cell.id),
            cell.code,
            cell.name,
            _config(cell.config),
        )
        for cell in session.document.cells
    ]
    return cells, session.app_file_manager.app.config.asdict_difference()


def from_file_manager(
    manager: AppFileManager,
) -> tuple[list[CellSource], dict[str, Any]]:
    cells = [
        CellSource(
            protocol.CellId(data.cell_id),
            data.code,
            data.name,
            _config(data.config),
        )
        for data in manager.app.cell_manager.cell_data()
    ]
    return cells, manager.app.config.asdict_difference()


def _config(config: CellConfig) -> protocol.CellConfig:
    return protocol.CellConfig(
        column=config.column,
        disabled=config.disabled,
        hide_code=config.hide_code,
        expand_output=config.expand_output,
    )


def _cell_config(config: protocol.CellConfig) -> CellConfig:
    return CellConfig(
        column=config.column,
        disabled=config.disabled,
        hide_code=config.hide_code,
        expand_output=config.expand_output,
    )


def to_notebook_cell(cell: protocol.Cell) -> NotebookCell:
    return NotebookCell(
        id=CellId_t(cell.id),
        code=cell.code,
        name=cell.name,
        config=_cell_config(cell.config),
    )


def apply_app_config(
    manager: AppFileManager, app_config: dict[str, Any]
) -> None:
    manager.app.update_config({**_AppConfig().asdict(), **app_config})


def apply_to_session(session: Session, document: Document) -> None:
    """Apply the document's state to the session as one transaction.

    The session tells its consumers, so the frontend sees the edit, and
    the host backend mirrors it back as a no-op.
    """
    current = session.document
    changes: list[DocumentChange] = []
    previous: str | None = None
    for cell in document:
        cell_id = CellId_t(cell.id)
        existing = current.get(cell_id)
        if existing is None:
            changes.append(
                CreateCell(
                    cell_id=cell_id,
                    code=cell.code,
                    name=cell.name,
                    config=_cell_config(cell.config),
                    after=None if previous is None else CellId_t(previous),
                )
            )
        else:
            if existing.code != cell.code:
                changes.append(SetCode(cell_id=cell_id, code=cell.code))
            if existing.name != cell.name:
                changes.append(SetName(cell_id=cell_id, name=cell.name))
            if _config(existing.config) != cell.config:
                changes.append(
                    SetConfig(
                        cell_id=cell_id,
                        column=cell.config.column,
                        disabled=cell.config.disabled,
                        hide_code=cell.config.hide_code,
                        expand_output=cell.config.expand_output,
                    )
                )
        previous = cell.id
    wanted = {str(cell.id) for cell in document}
    changes.extend(
        DeleteCell(cell_id=cell_id)
        for cell_id in current.cell_ids
        if cell_id not in wanted
    )
    if [c for c in current.cell_ids if c in wanted] != [
        CellId_t(c) for c in document.order
    ]:
        changes.append(
            ReorderCells(cell_ids=tuple(CellId_t(c) for c in document.order))
        )
    apply_app_config(session.app_file_manager, document._record.app_config)
    if not changes:
        return
    applied = current.apply(Transaction(changes=tuple(changes), source="host"))
    session.notify(
        NotebookDocumentTransactionNotification(transaction=applied),
        from_consumer_id=None,
    )
