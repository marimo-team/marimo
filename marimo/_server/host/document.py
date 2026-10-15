# Copyright 2026 Marimo. All rights reserved.
"""Translate between host records and the editor's document model.

The host owns protocol edits and etags. Sessions still own the editor's
transaction history, so the bridge mirrors each session transaction into
the host document.

While a session is attached it also owns the app config, and the host
document only mirrors it. Host edits change cells and their order.

TODO: An editor app config change produces no document transaction, so
the host does not learn of it until the next cell transaction, and
`app_config` and `app_config_etag` on the host stream lag until then.
Nothing writes app config from the host side, so no data is at risk.
Resolve once the frontend consumes the host protocol, when a config
change becomes a change on the core document like any other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
from marimo._runtime.commands import EditCellsCommand
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterable

    from marimo._core.document import Document
    from marimo._session.notebook import AppFileManager
    from marimo._session.session import Session


def from_session(session: Session) -> tuple[list[CellSource], dict[str, Any]]:
    return (
        sources(session.document.cells),
        session.app_file_manager.app.config.asdict_difference(),
    )


def sources(cells: Iterable[NotebookCell]) -> list[CellSource]:
    """The document sources for the editor's cells."""
    return [
        CellSource(cell.id, cell.code, cell.name, _config(cell.config))
        for cell in cells
    ]


def from_file_manager(
    manager: AppFileManager,
) -> tuple[list[CellSource], dict[str, Any]]:
    cells = [
        CellSource(data.cell_id, data.code, data.name, _config(data.config))
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


def apply_to_session(session: Session, document: Document) -> None:
    """Apply the document's cells and order to the session as one transaction.

    The session tells its consumers, so the frontend sees the edit and
    the host backend mirrors it back as a no-op. The kernel is told of
    the edit as one command, so nothing runs code the document no longer
    has: changed code is registered without running, and a cell the edit
    deletes or disables is gone before any run the deletion causes. The
    app config is the session's own and is left alone.
    """
    current = session.document
    changes: list[DocumentChange] = []
    codes: dict[CellId_t, str] = {}
    configs: dict[CellId_t, dict[str, Any]] = {}
    previous: CellId_t | None = None
    for cell in document:
        cell_id = CellId_t(cell.id)
        existing = current.get(cell_id)
        config = _cell_config(cell.config)
        if existing is None:
            changes.append(
                CreateCell(
                    cell_id=cell_id,
                    code=cell.code,
                    name=cell.name,
                    config=config,
                    after=previous,
                )
            )
            codes[cell_id] = cell.code
            if config != CellConfig():
                configs[cell_id] = config.asdict()
        else:
            if existing.code != cell.code:
                changes.append(SetCode(cell_id=cell_id, code=cell.code))
                codes[cell_id] = cell.code
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
                configs[cell_id] = config.asdict()
        previous = cell_id
    wanted = {CellId_t(cell.id) for cell in document}
    deleted = [c for c in current.cell_ids if c not in wanted]
    changes.extend(DeleteCell(cell_id=cell_id) for cell_id in deleted)
    order = [CellId_t(c) for c in document.order]
    if current.cell_ids != order:
        changes.append(ReorderCells(cell_ids=tuple(order)))
    if not changes:
        return
    applied = current.apply(Transaction(changes=tuple(changes), source="host"))
    session.notify(
        NotebookDocumentTransactionNotification(transaction=applied),
        from_consumer_id=None,
    )
    if codes or configs or deleted:
        session.put_control_request(
            EditCellsCommand(codes=codes, configs=configs, delete_ids=deleted),
            from_consumer_id=None,
        )
