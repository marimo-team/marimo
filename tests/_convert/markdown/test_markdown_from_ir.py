# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.app import App, InternalApp
from marimo._convert.markdown.flavor import (
    markdown_flavor_from_filename,
    normalize_markdown_flavor,
)
from marimo._convert.markdown.flavor.base import (
    CodeCellBlock,
    DirectiveBlock,
    MarkdownCellBlock,
    MarkdownExportDocument,
)
from marimo._convert.markdown.flavor.pymdown import split_pymdown_blocks
from marimo._convert.markdown.from_ir import (
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


def test_convert_from_ir_to_markdown_qmd_format():
    """Test that .qmd files use Quarto-compatible fence format."""
    app = App()

    @app.cell()
    def test_cell():
        x = 1
        return (x,)

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    # Test .qmd filename produces Quarto format
    markdown_qmd = convert_from_ir_to_markdown(
        notebook, filename="notebook.qmd"
    )
    assert "```{marimo .python" in markdown_qmd

    # Test .md filename produces standard format
    markdown_md = convert_from_ir_to_markdown(notebook, filename="notebook.md")
    # Should use either superfences or fallback format
    assert (
        "```python {.marimo" in markdown_md
        or "```{.python.marimo" in markdown_md
    )


def test_convert_from_ir_to_markdown_explicit_flavor():
    """Test that explicit flavors override filename inference."""
    app = App()

    @app.cell()
    def test_cell():
        x = 1
        return (x,)

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown_qmd = convert_from_ir_to_markdown(
        notebook, filename="notebook.md", flavor="qmd"
    )
    assert "```{marimo .python" in markdown_qmd

    markdown_md = convert_from_ir_to_markdown(
        notebook, filename="notebook.qmd", flavor="pymdown"
    )
    assert (
        "```python {.marimo" in markdown_md
        or "```{.python.marimo" in markdown_md
    )


def test_markdown_flavor_renders_export_document():
    """Test that the PyMdown flavor renders preamble and block syntax."""
    flavor = markdown_flavor_from_filename("notebook.md")
    assert flavor.name == "pymdown"
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock("# First"),
            MarkdownCellBlock("# Second"),
            CodeCellBlock("x = 1", "python", {}),
        ],
    )

    markdown = flavor.render_document(document)

    assert markdown.startswith("---\ntitle: Notebook\n---")
    assert "# First\n<!---->\n# Second\n\n" in markdown
    assert "x = 1" in markdown


def test_qmd_flavor_renders_export_document():
    """Test that qmd flavor renders executable fence syntax."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[CodeCellBlock("x = 1", "python", {})],
    )

    markdown = flavor.render_document(document)

    assert "filters:" not in markdown
    assert "```{marimo .python}" in markdown


def test_qmd_flavor_escapes_code_cell_attributes():
    """Test that qmd code fence attributes escape quotes and ampersands."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            CodeCellBlock(
                "x = 1",
                "python",
                {"name": 'a"b & c', "engine": 'duck&"db'},
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert 'name="a&quot;b &amp; c"' in markdown
    assert 'engine="duck&amp;&quot;db"' in markdown


def test_qmd_flavor_preserves_explicit_filters():
    """Test that qmd flavor serializes user-provided filters."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook", "filters": ["custom-filter"]},
        header=None,
        blocks=[CodeCellBlock("x = 1", "python", {})],
    )

    markdown = flavor.render_document(document)

    assert markdown.startswith(
        "---\ntitle: Notebook\nfilters:\n- custom-filter\n---\n"
    )


def test_qmd_flavor_maps_pymdown_admonitions_to_callouts():
    """Test that qmd flavor renders PyMdown admonitions as Quarto callouts."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """Before

/// attention | Careful

This needs attention.
///

After"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert '::: {.callout-important title="Careful"}' in markdown
    assert "This needs attention.\n:::" in markdown
    assert "Before\n\n::: {.callout-important" in markdown
    assert ":::\n\nAfter" in markdown


def test_qmd_flavor_preserves_plain_pymdown_callout_title():
    """Test that plain PyMdown callout titles stay unquoted in QMD."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// tip | Variables panel

Open the variables panel.
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert '::: {.callout-tip title="Variables panel"}' in markdown


def test_qmd_flavor_preserves_quoted_pymdown_callout_title():
    """Test that quoted PyMdown callout titles stay quoted in QMD."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// tip | "Variables panel"

Open the variables panel.
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert '::: {.callout-tip title="&quot;Variables panel&quot;"}' in markdown


def test_qmd_flavor_maps_generic_admonition_type_to_callout():
    """Test that generic PyMdown admonition type selects Quarto callout type."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// admonition | Heads up
    type: warning

Watch this.
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert '::: {.callout-warning title="Heads up"}' in markdown
    assert "Watch this.\n:::" in markdown


def test_pymdown_flavor_preserves_pymdown_admonitions():
    """Test that pymdown flavor keeps PyMdown syntax unchanged."""
    flavor = markdown_flavor_from_filename("notebook.md")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// tip | Keep this

PyMdown syntax is preserved.
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert "/// tip | Keep this" in markdown


def test_convert_from_ir_to_markdown_maps_admonitions_for_qmd():
    """Test full export maps PyMdown markdown admonitions for qmd output."""
    app = App()

    @app.cell()
    def __():
        import marimo as mo

        return (mo,)

    @app.cell()
    def __(mo):
        mo.md(
            """
            /// tip | Tip with Title

            This is an example.
            ///
            """
        )
        return

    internal_app = InternalApp(app)
    notebook = internal_app.to_ir()

    markdown = convert_from_ir_to_markdown(notebook, filename="notebook.qmd")

    assert '::: {.callout-tip title="Tip with Title"}' in markdown
    assert "This is an example.\n:::" in markdown


def test_qmd_flavor_maps_pymdown_tabs_to_panel_tabsets():
    """Test that consecutive PyMdown tabs become a Quarto panel tabset."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// tab | Python
print("py")
///

/// tab | SQL
    select: true

select 1
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert "::: {.panel-tabset}" in markdown
    assert '## Python\n\nprint("py")' in markdown
    assert "## SQL {.active}\n\nselect 1" in markdown


def test_qmd_flavor_starts_new_tabset_for_pymdown_new_tab_option():
    """Test that PyMdown tab new option starts another Quarto tabset."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// tab | A
A
///

/// tab | B
    new: true

B
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert markdown.count("::: {.panel-tabset}") == 2
    assert "## A\n\nA" in markdown
    assert "## B\n\nB" in markdown


def test_qmd_flavor_falls_back_to_pandoc_divs():
    """Test that unmapped PyMdown directives become Quarto-compatible divs."""
    flavor = markdown_flavor_from_filename("notebook.qmd")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// details | More
    attrs: {id: more, class: folded quiet}
    open: true

Body
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert (
        '::: {.details title="More" #more .folded .quiet open="true"}'
        in markdown
    )
    assert "Body\n:::" in markdown


def test_split_pymdown_blocks_keeps_directives_inside_markdown_fences():
    """Test that literal directives inside code fences are not parsed."""
    blocks = split_pymdown_blocks(
        """```text
literal
``` not a closing fence
/// tip | Should stay code
body
///
```

/// tip | Real
body
///"""
    )

    assert len(blocks) == 2
    assert isinstance(blocks[0], MarkdownCellBlock)
    assert "/// tip | Should stay code" in blocks[0].text
    assert isinstance(blocks[1], DirectiveBlock)
    assert blocks[1].argument == "Real"


def test_split_pymdown_blocks_preserves_body_colon_lines():
    """Test that body-leading colon lines are not consumed as options."""
    blocks = split_pymdown_blocks(
        """/// details | Example
    key: value
    still body
///"""
    )

    assert len(blocks) == 1
    assert isinstance(blocks[0], DirectiveBlock)
    assert blocks[0].options == {}
    assert blocks[0].body == "    key: value\n    still body"


def test_mystmd_flavor_maps_pymdown_blocks_to_myst_directives():
    """Test that mystmd flavor maps PyMdown blocks to MyST directives."""
    flavor = normalize_markdown_flavor("mystmd", filename="notebook.md")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// tip | Nice
Body
///

/// tab | Python
print("py")
///

/// tab | SQL
select 1
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert ":::{tip} Nice\nBody\n:::" in markdown
    assert "::::{tab-set}" in markdown
    assert ':::{tab-item} Python\nprint("py")\n:::' in markdown
    assert ":::{tab-item} SQL\nselect 1\n:::" in markdown


def test_mystmd_flavor_renders_marimo_notebook_export_syntax():
    """Test that mystmd flavor renders marimo notebook authoring syntax."""
    flavor = normalize_markdown_flavor("mystmd", filename="notebook.md")
    pep723_header = (
        "import os",
        "# /// script",
        '# requires-python = ">=3.10"',
        "# dependencies = [",
        '#   "pandas",',
        "# ]",
        "# ///",
    )
    document = MarkdownExportDocument(
        metadata={
            "title": "Notebook",
            "marimo-version": "0.0.0",
            "width": "medium",
            "header": "\n".join(pep723_header),
        },
        header=None,
        blocks=[
            CodeCellBlock(
                source="x = 1",
                language="python",
                options={"hide_code": "true", "unparsable": "true"},
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert markdown.startswith("---\ntitle: Notebook\n---\n")
    assert "```{marimo-config}\n---\n" in markdown
    assert "header: |-\n  import os" in markdown
    assert 'requires-python = ">=3.10"' in markdown
    expected_cell = (
        "```{marimo} python",
        ":hide-code: true",
        ":unparsable: true",
        "",
        "x = 1",
        "```",
    )
    assert "\n".join(expected_cell) in markdown


def test_mystmd_flavor_grows_code_fence_guard():
    """Test that mystmd code fences are valid when source contains backticks."""
    flavor = normalize_markdown_flavor("mystmd", filename="notebook.md")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            CodeCellBlock(
                source='mo.md("""\n```python\nx = 1\n```\n""")',
                language="python",
                options={},
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert "````{marimo} python" in markdown
    assert markdown.rstrip().endswith("````")


def test_mystmd_flavor_merges_classes_into_one_option():
    """Test that MyST directives do not repeat the class option."""
    flavor = normalize_markdown_flavor("mystmd", filename="notebook.md")
    document = MarkdownExportDocument(
        metadata={"title": "Notebook"},
        header=None,
        blocks=[
            MarkdownCellBlock(
                """/// admonition | Heads up
    type: tip
    attrs: {class: extra}

Body
///"""
            )
        ],
    )

    markdown = flavor.render_document(document)

    assert (
        ":::{admonition} Heads up\n:class: tip extra\n\nBody\n:::" in markdown
    )
