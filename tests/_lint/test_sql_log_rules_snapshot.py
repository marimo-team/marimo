# Copyright 2025 Marimo. All rights reserved.
"""Snapshot tests for SQL log message lint rules."""

import pytest

from marimo._ast.parse import parse_notebook
from tests._lint.utils import lint_notebook
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


# Only run this in 3.12 since the formatting may differ in other versions
@pytest.mark.skipif("sys.version_info != (3, 12)")
def test_sql_parsing_errors_snapshot():
    """Test snapshot for SQL parsing log errors with positioning."""
    file = "tests/_lint/test_files/sql_parsing_errors.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    log_errors = [
        error for error in errors if error.code in ("MF005", "MF006")
    ]

    # Format errors for snapshot
    error_output = []
    for error in log_errors:
        error_output.append(error.format())

    if not error_output:
        error_output = ["No SQL log errors found"]

    snapshot("sql_parsing_errors.txt", "\n".join(error_output))
