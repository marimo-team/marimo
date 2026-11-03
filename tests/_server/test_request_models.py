import msgspec
import pytest

from marimo._ast.cell import CellConfig
from marimo._server.models.models import (
    ExecuteCellsRequest,
    SaveNotebookRequest,
)


def test_execute_cells_rejects_mismatched_cell_ids():
    with pytest.raises(
        msgspec.ValidationError, match="Mismatched cell_ids and codes"
    ):
        ExecuteCellsRequest(cell_ids=["a"], codes=[])


@pytest.mark.parametrize("field", ["codes", "names", "configs"])
def test_save_notebook_rejects_mismatched_cell_ids(field):
    kwargs = {
        "cell_ids": ["a"],
        "codes": [""],
        "names": [""],
        "configs": [CellConfig()],
        "filename": "notebook.py",
    }
    kwargs[field] = []

    with pytest.raises(
        msgspec.ValidationError, match=f"Mismatched cell_ids and {field}"
    ):
        SaveNotebookRequest(**kwargs)
