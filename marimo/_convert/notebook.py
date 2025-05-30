from marimo import __version__
from marimo._ast.app import InternalApp
from marimo._ast.load import load_app
from marimo._schemas.notebook import (
    NotebookCell,
    NotebookCellConfig,
    NotebookMetadata,
    NotebookV1,
)


def convert_from_py_to_notebook_v1(file_path: str, /) -> NotebookV1:
    """Convert a Python source code to a notebook session.

    Args:
        file_path (str): The path to the Python file to convert.

    Returns:
        str: The notebook session.
    """
    app = load_app(file_path)
    if app is None:
        raise ValueError("Failed to load app")
    internal_app = InternalApp(app)

    cells: list[NotebookCell] = []
    for data in internal_app.cell_manager.cell_data():
        cells.append(
            NotebookCell(
                id=data.cell_id,
                code=data.code,
                name=data.name,
                config=NotebookCellConfig(
                    column=data.config.column,
                    disabled=data.config.disabled,
                    hide_code=data.config.hide_code,
                ),
            )
        )
    return NotebookV1(
        version="1",
        cells=cells,
        metadata=NotebookMetadata(marimo_version=__version__),
    )
