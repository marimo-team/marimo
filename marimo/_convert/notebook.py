# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell_id import CellIdGenerator
from marimo._ast.names import SETUP_CELL_NAME
from marimo._schemas.notebook import (
    NotebookCell,
    NotebookCellConfig,
    NotebookMetadata,
    NotebookV1,
)
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    NotebookSerialization,
    NotebookSerializationV1,
    SetupCell,
)
from marimo._utils.code import hash_code
from marimo._version import __version__


def convert_from_ir_to_notebook_v1(
    notebook_ir: NotebookSerialization,
) -> NotebookV1:
    """Convert the notebook IR to the NotebookV1.

    Args:
        notebook_ir: The notebook IR.

    Returns:
        NotebookV1: The notebook v1.
    """
    cell_id_generator = CellIdGenerator()
    cells: list[NotebookCell] = []
    for i, data in enumerate(notebook_ir.cells):
        if isinstance(data, SetupCell) or (
            i == 0 and data.name == SETUP_CELL_NAME
        ):
            cell_id = SETUP_CELL_NAME
        else:
            cell_id = cell_id_generator.create_cell_id()
        cells.append(
            NotebookCell(
                id=cell_id,
                code=data.code,
                code_hash=hash_code(data.code) if data.code else None,
                name=data.name,
                config=NotebookCellConfig(
                    column=data.options.get("column", None),
                    disabled=data.options.get("disabled", False),
                    hide_code=data.options.get("hide_code", False),
                ),
            )
        )
    return NotebookV1(
        version="1",
        cells=cells,
        metadata=NotebookMetadata(marimo_version=__version__),
    )


def convert_from_notebook_v1_to_ir(
    notebook_v1: NotebookV1,
) -> NotebookSerialization:
    """Convert the notebook v1 to the python source code.

    Args:
        notebook_v1: The notebook v1.

    Returns:
        str: The python source code.
    """

    return NotebookSerializationV1(
        app=AppInstantiation(options={}),
        header=None,
        version=None,
        cells=[
            CellDef(
                code=cell.get("code", "") or "",
                name=cell.get("name", "") or "",
                options={
                    "column": cell.get("config", {}).get("column", None),
                    "disabled": cell.get("config", {}).get("disabled", False),
                    "hide_code": cell.get("config", {}).get(
                        "hide_code", False
                    ),
                },
            )
            for cell in notebook_v1.get("cells", [])
        ],
        violations=[],
        valid=True,
    )
