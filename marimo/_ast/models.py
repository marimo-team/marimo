# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from marimo._ast.cell import Cell, CellConfig
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
        lineno: Starting line number in the Python script file (0 if not from file)
        end_lineno: Ending line number in the Python script file (0 if not from file)
    """

    cell_id: CellId_t
    code: str
    name: str
    config: CellConfig
    cell: Optional[Cell]
    lineno: int = 0
    end_lineno: int = 0
