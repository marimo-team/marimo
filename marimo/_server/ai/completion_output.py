# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pydantic import BaseModel, Field

from marimo._server.models.completion import Language

CELL_COMPLETION_DATA_TYPE = "data-cell-completion"
NOTEBOOK_CELLS_COMPLETION_DATA_TYPE = "data-notebook-cells-completion"


class CellCompletion(BaseModel):
    """A replacement for the code in one notebook cell."""

    code: str = Field(description="Raw cell code without Markdown fences.")


class GeneratedCell(BaseModel):
    """A notebook cell generated from the user's request."""

    language: Language
    code: str = Field(description="Raw cell code without Markdown fences.")


class NotebookCellsCompletion(BaseModel):
    """The ordered notebook cells generated from the user's request."""

    cells: list[GeneratedCell]
