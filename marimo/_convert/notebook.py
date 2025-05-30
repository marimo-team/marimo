from marimo import __version__
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
)


def convert_from_ir_to_notebook_v1(
    notebook_ir: NotebookSerialization,
) -> NotebookV1:
    """Convert the notebook IR to the NotebookV1.

    Args:
        notebook_ir: The notebook IR.

    Returns:
        NotebookV1: The notebook v1.
    """
    cells: list[NotebookCell] = []
    for data in notebook_ir.cells:
        cells.append(
            NotebookCell(
                id=None,
                code=data.code,
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
