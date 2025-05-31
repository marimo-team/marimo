# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import Cell, CellConfig
from marimo._schemas.serialization import NotebookSerialization
from marimo._types.ids import CellId_t


@dataclass
class CellData:
    """A cell together with its metadata.

    This class bundles a cell with its associated metadata like ID, code, name and config.
    It represents both valid cells that can be executed and invalid/unparsable cells.

    Attributes:
        cell_id: Unique identifier for the cell
        code: Raw source code text of the cell
        name: User-provided name for the cell, or a default if none provided
        config: Configuration options for the cell like column placement, disabled state, etc.
        cell: The compiled Cell object if code is valid, None if code couldn't be parsed
    """

    cell_id: CellId_t
    code: str
    name: str
    config: CellConfig
    cell: Optional[Cell]


@dataclass
class NotebookPayload:
    """
    Dataclass for passing around a bundle of notebook data. Easier than arg drilling.
    """

    codes: list[str]
    names: list[str]
    cell_configs: list[CellConfig]
    config: Optional[_AppConfig] = None
    header_comments: Optional[str] = None

    @staticmethod
    def from_ir(serialization: NotebookSerialization) -> NotebookPayload:
        return NotebookPayload(
            codes=[cell.code for cell in serialization.cells],
            names=[cell.name for cell in serialization.cells],
            cell_configs=[
                CellConfig.from_dict(cell.options)
                for cell in serialization.cells
            ],
            config=_AppConfig.from_untrusted_dict(serialization.app.options),
            header_comments=serialization.header.value
            if serialization.header
            else None,
        )
