# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.app import App, InternalApp
from marimo._convert.markdown import (
    _format_filename_title,
    _get_sql_options_from_cell,
    convert_from_ir_to_markdown,
)


def test_format_filename_title():
    """Test that filenames are formatted correctly into titles."""
    assert _format_filename_title("my_notebook.py") == "My Notebook"
    assert _format_filename_title("my-notebook.md") == "My Notebook"
    assert _format_filename_title("/path/to/my_notebook.py") == "My Notebook"
    assert _format_filename_title("simple.py") == "Simple"
    assert _format_filename_title("my-cool_notebook.md") == "My Cool Notebook"


def test_get_sql_options_from_cell_basic():
    """Test extraction of SQL options from basic SQL code."""
    code = '_df = mo.sql("SELECT * FROM table")'
    options = _get_sql_options_from_cell(code)
    assert options is not None
    assert options["query"] == "_df"


def test_get_sql_options_from_cell_with_keywords():
    """Test extraction of SQL options with keyword arguments."""
    code = '_df = mo.sql("SELECT * FROM table", output=False)'
    options = _get_sql_options_from_cell(code)
    assert options is not None
    assert options["query"] == "_df"
    assert options["hide_output"] == "True"


def test_get_sql_options_from_cell_with_engine():
    """Test extraction of SQL options with engine parameter."""
    code = 'result = mo.sql("SELECT * FROM table", engine="my_engine")'
    options = _get_sql_options_from_cell(code)
    assert options is not None
    assert options["query"] == "result"
    assert options["engine"] == "my_engine"


def test_get_sql_options_from_cell_not_sql():
    """Test that non-SQL code returns None."""
    code = "x = 1 + 1"
    options = _get_sql_options_from_cell(code)
    assert options is None


def test_get_sql_options_from_cell_invalid():
    """Test that code without proper structure returns None."""
    code = 'x = mo.other_method("SELECT * FROM table")'
    options = _get_sql_options_from_cell(code)
    assert options is None


def test_get_sql_options_from_cell_not_assignment():
    """Test that code without assignment returns None."""
    code = 'mo.sql("SELECT * FROM table")'
    options = _get_sql_options_from_cell(code)
    assert options is None


def test_convert_from_ir_to_markdown_empty():
    """Test conversion of empty notebook to markdown."""
    app = App()
    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Should have frontmatter
    assert markdown.startswith("---")
    assert "marimo-version" in markdown


def test_convert_from_ir_to_markdown_with_code():
    """Test conversion of notebook with code cells to markdown."""
    app = App()

    @app.cell()
    def test_cell():
        x = 1
        return (x,)

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Should have frontmatter
    assert markdown.startswith("---")
    assert "marimo-version" in markdown
    # Should have code block
    assert "```python" in markdown
    assert "x = 1" in markdown


def test_convert_from_ir_to_markdown_with_markdown_cell():
    """Test conversion of notebook with markdown cells."""
    app = App()

    @app.cell()
    def __():
        import marimo as mo

        return (mo,)

    @app.cell()
    def __(mo):
        mo.md("# Hello World")
        return

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Should have the markdown content
    assert "# Hello World" in markdown


def test_convert_from_ir_to_markdown_with_sql():
    """Test conversion of notebook with SQL cells to markdown."""
    app = App()

    @app.cell()
    def __():
        import marimo as mo

        return (mo,)

    @app.cell()
    def __(mo):
        _df = mo.sql("SELECT * FROM my_table")
        return (_df,)

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Should have SQL code block
    assert "```sql" in markdown or "```python" in markdown
    assert "SELECT * FROM my_table" in markdown


def test_convert_from_ir_to_markdown_preserves_cell_names():
    """Test that cell names are preserved in markdown."""
    app = App()

    @app.cell()
    def my_cell():
        x = 1
        return (x,)

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Should have cell name in attributes
    assert "name=my_cell" in markdown or 'name="my_cell"' in markdown


def test_convert_from_ir_to_markdown_with_cell_config():
    """Test that cell configurations are preserved."""
    app = App()

    @app.cell(hide_code=True)
    def __():
        x = 1
        return (x,)

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Should have hide_code in attributes
    assert 'hide_code="true"' in markdown or "hide_code=true" in markdown


def test_convert_from_ir_to_markdown_with_app_title():
    """Test that app title is preserved in frontmatter."""
    app = App(app_title="My Test App")

    @app.cell()
    def __():
        return

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Should have title in frontmatter
    assert "title: My Test App" in markdown


def test_convert_from_ir_to_markdown_consecutive_markdown_cells():
    """Test that consecutive markdown cells are separated with HTML comments."""
    app = App()

    @app.cell()
    def __():
        import marimo as mo

        return (mo,)

    @app.cell()
    def __(mo):
        mo.md("# First markdown")
        return

    @app.cell()
    def __(mo):
        mo.md("# Second markdown")
        return

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Should have HTML comment separator between markdown cells
    assert "<!---->" in markdown
    assert "# First markdown" in markdown
    assert "# Second markdown" in markdown


def test_convert_from_ir_to_markdown_with_column():
    """Test that cells with column configuration force markdown to code."""
    app = App()

    @app.cell()
    def __():
        import marimo as mo

        return (mo,)

    @app.cell(column=1)
    def __(mo):
        mo.md("# Markdown in column")
        return

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook)

    # Markdown should be forced to code block due to column
    assert "```python" in markdown
    assert "column=1" in markdown or 'column="1"' in markdown


def test_convert_from_ir_to_markdown_unparsable_cell():
    """Test that unparsable cells are marked with unparsable attribute."""
    from marimo._schemas.serialization import (
        AppInstantiation,
        CellDef,
        NotebookSerializationV1,
    )

    # Create a notebook with an unparsable cell by directly constructing the IR
    notebook = NotebookSerializationV1(
        app=AppInstantiation(options={}),
        cells=[
            CellDef(
                name="__",
                code="this is { not valid python",
                options={},
            )
        ],
        violations=[],
        valid=True,
        filename="notebook.py",
    )

    markdown = convert_from_ir_to_markdown(notebook)

    # Should mark as unparsable
    assert 'unparsable="true"' in markdown or "unparsable=true" in markdown
    assert "this is { not valid python" in markdown
