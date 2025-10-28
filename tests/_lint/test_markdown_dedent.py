# Copyright 2025 Marimo. All rights reserved.
"""Tests for markdown dedent lint rule."""

from marimo._ast.parse import parse_notebook
from tests._lint.utils import lint_notebook


def test_markdown_dedent_detection():
    """Test that markdown dedent rule detects indented markdown."""
    file = "tests/_lint/test_files/markdown_dedent.py"
    with open(file) as f:
        code = f.read()

    notebook = parse_notebook(code, filepath=file)
    errors = lint_notebook(notebook)

    # Should have MF007 errors for indented markdown cells
    mf007_errors = [e for e in errors if e.code == "MF007"]
    assert len(mf007_errors) > 0, "Should detect indented markdown"


def test_markdown_dedent_over_indent():
    """Test that correctly formatted markdown doesn't trigger the rule."""
    code = """
import marimo

__generated_with = "0.17.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(\"\"\"
# This is overly dedented

and incorrect.
\"\"\")
    return


if __name__ == "__main__":
    app.run()
"""
    notebook = parse_notebook(code)
    errors = lint_notebook(notebook, code)

    # Should not have MF007 errors for properly dedented markdown
    mf007_errors = [e for e in errors if e.code == "MF007"]
    assert len(mf007_errors) == 1, (
        "Should not flag correctly dedented markdown"
    )


def test_markdown_dedent_no_false_positives():
    """Test that correctly formatted markdown doesn't trigger the rule."""
    code = """
import marimo

__generated_with = "0.17.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(\"\"\"
    # Already dedented

    This is correct.
    \"\"\")
    return


if __name__ == "__main__":
    app.run()
"""
    notebook = parse_notebook(code)
    errors = lint_notebook(notebook, code)

    # Should not have MF007 errors for properly dedented markdown
    mf007_errors = [e for e in errors if e.code == "MF007"]
    assert len(mf007_errors) == 0, (
        "Should not flag correctly dedented markdown"
    )
