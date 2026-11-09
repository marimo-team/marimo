# Copyright 2026 Marimo. All rights reserved.
"""Document requests exchanged by a kernel and its host."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import msgspec

from marimo._ast.cell import CellConfig
from marimo._core import protocol
from marimo._core.document import Document, DocumentCell

if TYPE_CHECKING:
    from collections.abc import Iterable

    from marimo._messaging.notebook.document import NotebookCell


class DocumentSnapshot(msgspec.Struct, frozen=True):
    cells: tuple[DocumentCell, ...]
    app_config: dict[str, Any]

    def document(self) -> Document:
        return Document(self.cells, self.app_config)


class DocumentRequest(
    msgspec.Struct, frozen=True, tag_field="op", tag="host-document-request"
):
    """Read or edit the notebook bound to a scratchpad execution.

    `for_run` checks pending updates before committing an edit-and-run batch.
    `applied_edits` names queued updates already applied inline by the kernel.
    """

    name: ClassVar[str] = "host-document-request"
    request_id: str
    changes: tuple[protocol.Change, ...] | None = None
    cells: tuple[protocol.RequestedCell, ...] = ()
    for_run: bool = False
    applied_edits: tuple[str, ...] = ()


def sources(cells: Iterable[NotebookCell]) -> list[DocumentCell]:
    """The document sources for the editor's cells."""
    return [
        DocumentCell(
            protocol.CellId(cell.id),
            cell.code,
            cell.name,
            document_config(cell.config),
        )
        for cell in cells
    ]


def document_config(config: CellConfig) -> protocol.CellConfig:
    return protocol.CellConfig(
        column=config.column,
        disabled=config.disabled,
        hide_code=config.hide_code,
        expand_output=config.expand_output,
    )


def runtime_config(config: protocol.CellConfig) -> CellConfig:
    return CellConfig(
        column=config.column,
        disabled=config.disabled,
        hide_code=config.hide_code,
        expand_output=config.expand_output,
    )
