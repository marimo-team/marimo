# Copyright 2025 Marimo. All rights reserved.
"""Snapshot tests for empty cells lint rule."""

from marimo._ast.parse import parse_notebook
from tests._lint.utils import lint_notebook
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_empty_cells_detection_snapshot():
    """Test snapshot for empty cells detection."""
    file = "tests/_lint/test_files/empty_cells.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("empty_cells.txt", "\n".join(error_output))
