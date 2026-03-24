# Copyright 2026 Marimo. All rights reserved.
"""Typed operations and transactions for notebook structural changes."""

from __future__ import annotations

from typing import Literal, Optional, Union

import msgspec

from marimo._ast.cell import CellConfig
from marimo._types.ids import CellId_t

# ------------------------------------------------------------------
# Structural ops (change the cell list)
# ------------------------------------------------------------------


class CreateCell(
    msgspec.Struct, frozen=True, tag="create-cell", rename="camel"
):
    """Insert a new cell into the notebook."""

    cell_id: CellId_t
    code: str
    name: str
    config: CellConfig
    before: Optional[CellId_t] = None
    after: Optional[CellId_t] = None


class DeleteCell(
    msgspec.Struct, frozen=True, tag="delete-cell", rename="camel"
):
    """Remove a cell from the notebook."""

    cell_id: CellId_t


class MoveCell(msgspec.Struct, frozen=True, tag="move-cell", rename="camel"):
    """Reposition a cell in the notebook."""

    cell_id: CellId_t
    before: Optional[CellId_t] = None
    after: Optional[CellId_t] = None


class ReorderCells(
    msgspec.Struct, frozen=True, tag="reorder-cells", rename="camel"
):
    """Replace the full cell ordering.

    Cell IDs present in the document but missing from ``cell_ids``
    are appended at the end. IDs not in the document are ignored.
    """

    cell_ids: tuple[CellId_t, ...]


# ------------------------------------------------------------------
# Property ops (change cell content)
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
    column: Optional[int] = None
    disabled: Optional[bool] = None
    hide_code: Optional[bool] = None


Op = Union[
    CreateCell, DeleteCell, MoveCell, ReorderCells, SetCode, SetName, SetConfig
]

# ------------------------------------------------------------------
# Transaction
# ------------------------------------------------------------------


class Transaction(msgspec.Struct, frozen=True, rename="camel"):
    """An atomic batch of operations applied to a NotebookDocument.

    ``source`` identifies the writer (e.g. ``"frontend"``, ``"kernel"``).
    ``version`` is ``None`` when created and stamped by
    ``NotebookDocument.apply()``.
    """

    ops: tuple[Op, ...]
    source: Literal["frontend", "kernel"]
    version: Optional[int] = None
