# Copyright 2026 Marimo. All rights reserved.
"""Typed operations and transactions for notebook structural changes."""

from __future__ import annotations

from typing import Literal

import msgspec

from marimo._ast.cell import CellConfig
from marimo._types.ids import CellId_t

# ------------------------------------------------------------------
# Structural changes (change the cell list)
# ------------------------------------------------------------------


class CreateCell(
    msgspec.Struct, frozen=True, tag="create-cell", rename="camel"
):
    """Insert a new cell into the notebook."""

    cell_id: CellId_t
    code: str
    name: str
    config: CellConfig
    before: CellId_t | None = None
    after: CellId_t | None = None


class DeleteCell(
    msgspec.Struct, frozen=True, tag="delete-cell", rename="camel"
):
    """Remove a cell from the notebook."""

    cell_id: CellId_t


class MoveCell(msgspec.Struct, frozen=True, tag="move-cell", rename="camel"):
    """Reposition a cell in the notebook."""

    cell_id: CellId_t
    before: CellId_t | None = None
    after: CellId_t | None = None


class ReorderCells(
    msgspec.Struct, frozen=True, tag="reorder-cells", rename="camel"
):
    """Replace the full cell ordering.

    Cell IDs present in the document but missing from ``cell_ids``
    are appended at the end. IDs not in the document are ignored.
    """

    cell_ids: tuple[CellId_t, ...]


# ------------------------------------------------------------------
# Property changes (change cell content)
# ------------------------------------------------------------------


class SetCode(msgspec.Struct, frozen=True, tag="set-code", rename="camel"):
    """Replace a cell's source code."""

    cell_id: CellId_t
    code: str


class SetName(msgspec.Struct, frozen=True, tag="set-name", rename="camel"):
    """Rename a cell."""

    cell_id: CellId_t
    name: str


class SetConfig(msgspec.Struct, frozen=True, tag="set-config", rename="camel"):
    """Partially update a cell's config. None fields are unchanged."""

    cell_id: CellId_t
    column: int | None = None
    disabled: bool | None = None
    hide_code: bool | None = None


DocumentChange = (
    CreateCell
    | DeleteCell
    | MoveCell
    | ReorderCells
    | SetCode
    | SetName
    | SetConfig
)

# ------------------------------------------------------------------
# Transaction
# ------------------------------------------------------------------

TransactionSource = Literal[
    "frontend", "kernel", "code-mode", "file-watch", "cell_manager"
]


class Transaction(msgspec.Struct, frozen=True, rename="camel"):
    """An atomic batch of changes applied to a NotebookDocument.

    ``source`` identifies the writer (e.g. ``"frontend"``, ``"kernel"``).
    ``version`` is ``None`` when created and stamped by
    ``NotebookDocument.apply()``.
    """

    changes: tuple[DocumentChange, ...]
    source: TransactionSource
    version: int | None = None
