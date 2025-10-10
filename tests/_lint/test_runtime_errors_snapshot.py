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


def test_star_import_snapshot():
    """Test snapshot for star import syntax errors with enhanced hints."""
    file = "tests/_lint/test_files/star_import.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("star_import_errors.txt", "\n".join(error_output))


def test_self_import_pandas_snapshot(tmp_path):
    """Test snapshot for self-import pandas error."""
    source_file = "tests/_lint/test_files/self_import_conflict.py"
    with open(source_file) as f:
        code = f.read()

    # Create file with conflicting name in temporary directory
    conflicting_file = tmp_path / "pandas.py"
    conflicting_file.write_text(code)

    notebook = parse_notebook(code, filepath=str(conflicting_file))
    errors = lint_notebook(notebook)

    # Format errors for snapshot - manually normalize paths to avoid tmp path differences
    error_output = []
    for error in errors:
        formatted = error.format()
        # Replace temporary path with expected test path for consistent snapshots
        # Normalize path separators to forward slashes for cross-platform compatibility
        normalized = formatted.replace(
            str(tmp_path), "tests/_lint/test_files"
        ).replace("\\", "/")
        error_output.append(normalized)

    snapshot("self_import_pandas_errors.txt", "\n".join(error_output))


def test_transitive_site_import_snapshot(tmp_path):
    """Test snapshot for transitive site import error."""
    source_file = "tests/_lint/test_files/test_transitive_site_import.py"
    with open(source_file) as f:
        code = f.read()

    # Create file with conflicting name in temporary directory
    # This file imports pandas, so we need to create a pandas.py file to trigger the conflict
    conflicting_file = tmp_path / "pandas.py"
    conflicting_file.write_text(code)

    notebook = parse_notebook(code, filepath=str(conflicting_file))
    errors = lint_notebook(notebook)

    # Format errors for snapshot - manually normalize paths to avoid tmp path differences
    error_output = []
    for error in errors:
        formatted = error.format()
        # Replace temporary path with expected test path for consistent snapshots
        # Normalize path separators to forward slashes for cross-platform compatibility
        normalized = formatted.replace(
            str(tmp_path), "tests/_lint/test_files"
        ).replace("\\", "/")
        error_output.append(normalized)

    snapshot("transitive_site_import_errors.txt", "\n".join(error_output))


def test_self_import_requests_snapshot(tmp_path):
    """Test snapshot for self-import requests error."""
    source_file = "tests/_lint/test_files/module_shadow.py"
    with open(source_file) as f:
        code = f.read()

    # Create file with conflicting name in temporary directory
    conflicting_file = tmp_path / "requests.py"
    conflicting_file.write_text(code)

    notebook = parse_notebook(code, filepath=str(conflicting_file))
    errors = lint_notebook(notebook)

    # Format errors for snapshot - manually normalize paths to avoid tmp path differences
    error_output = []
    for error in errors:
        formatted = error.format()
        # Replace temporary path with expected test path for consistent snapshots
        # Normalize path separators to forward slashes for cross-platform compatibility
        normalized = formatted.replace(
            str(tmp_path), "tests/_lint/test_files"
        ).replace("\\", "/")
        error_output.append(normalized)

    snapshot("self_import_requests_errors.txt", "\n".join(error_output))


def test_mixed_issues_snapshot():
    """Test snapshot for mixed issues (syntax errors + multiple definitions)."""
    file = "tests/_lint/test_files/mixed_issues.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Format errors for snapshot
    error_output = []
    for error in errors:
        error_output.append(error.format())

    snapshot("mixed_issues_errors.txt", "\n".join(error_output))
