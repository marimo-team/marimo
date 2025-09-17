# Copyright 2025 Marimo. All rights reserved.
"""Snapshot tests for runtime lint errors."""

from marimo._ast.parse import parse_notebook
from tests._lint.utils import lint_notebook
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_multiple_definitions_snapshot():
    """Test snapshot for multiple definitions error."""
    file = "tests/_lint/test_files/multiple_definitions.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("multiple_definitions_errors.txt", "\n".join(error_output))


def test_cycle_dependencies_snapshot():
    """Test snapshot for cycle dependencies error."""
    file = "tests/_lint/test_files/cycle_dependencies.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("cycle_dependencies_errors.txt", "\n".join(error_output))


def test_setup_dependencies_snapshot():
    """Test snapshot for setup dependencies error."""
    file = "tests/_lint/test_files/setup_dependencies.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("setup_dependencies_errors.txt", "\n".join(error_output))


def test_unparsable_cell_snapshot():
    """Test snapshot for unparsable cell error."""
    file = "tests/_lint/test_files/unparsable_cell.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("unparsable_cell_errors.txt", "\n".join(error_output))


def test_formatting_snapshot():
    """Test snapshot for unparsable cell error."""
    file = "tests/_lint/test_files/formatting.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("formatting.txt", "\n".join(error_output))


def test_syntax_errors_snapshot():
    """Test snapshot for syntax errors."""
    file = "tests/_lint/test_files/syntax_errors.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("syntax_errors.txt", "\n".join(error_output))
