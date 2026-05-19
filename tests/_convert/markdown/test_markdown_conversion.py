# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from marimo import __version__
from marimo._ast.app import InternalApp
from marimo._ast.load import load_notebook_ir
from marimo._convert.converters import MarimoConvert
from marimo._convert.markdown.from_ir import convert_from_ir_to_markdown
from marimo._convert.markdown.to_ir import (
    convert_from_md_to_marimo_ir,
)
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    Header,
    NotebookSerializationV1,
)

# Just a handful of scripts to test
from marimo._tutorials import dataflow, for_jupyter_users, sql
from tests.mocks import snapshotter

modules = {
    "marimo_for_jupyter_users": for_jupyter_users,
    "dataflow": dataflow,
    "sql": sql,
}

DIR_PATH = os.path.dirname(os.path.realpath(__file__))

snapshot = snapshotter(__file__)


def md_to_py(md: str) -> str:
    if not md:
        return ""
    return MarimoConvert.from_md(md).to_py()


def sanitized_version(output: str) -> str:
    return output.replace(__version__, "0.0.0")


def convert_from_py_to_md(py: str) -> str:
    output = MarimoConvert.from_py(py).to_markdown(filename="Test Notebook")
    return sanitized_version(output)


# Regarding windows skip: This should be fine, as less complex cases are
# captured by test_markdown_frontmatter. Here, snapshotting fails in windows
# due to emojis in the tutorials :(
@pytest.mark.skipif(
    sys.platform == "win32", reason="Failing on Windows CI due to emojis"
)
def test_markdown_snapshots() -> None:
    for name, mod in modules.items():
        py_contents = Path(str(mod.__file__)).read_text(encoding="utf-8")
        converter = MarimoConvert.from_py(py_contents)
        output = converter.to_markdown(filename=f"{name}.py")
        snapshot(f"{name}.md.txt", output)


# Windows does not encode emojis correctly for md -> python
@pytest.mark.skipif(
    sys.platform == "win32", reason="Failing on Windows CI due to emojis"
)
def test_idempotent_markdown_to_marimo() -> None:
    for script in modules:
        with open(DIR_PATH + f"/snapshots/{script}.md.txt") as f:
            md = f.read()
        python_source = sanitized_version(md_to_py(md))
        assert convert_from_py_to_md(python_source) == md.strip()


def test_markdown_frontmatter() -> None:
    script = dedent(
        remove_empty_lines(
            """
    ---
    title: "My Title"
    description: "My Description"
    tags: ["tag1", "tag2"]
    filters:
    - name: "filter1"
    - name: "filter2"
    header: |
        #!/usr/bin/env python
        # and some other random stuff
    ---

    # Notebook

    ```python {.marimo}
    print("Hello, World!")
    ```
    """
        )
    )

    # As python file
    output = sanitized_version(md_to_py(script))
    assert 'app_title="My Title"' in output
    assert output.startswith("#!/usr/bin/env python")
    snapshot("frontmatter-test.py.txt", output)

    # As python object
    notebook_ir = convert_from_md_to_marimo_ir(script)
    app = InternalApp(load_notebook_ir(notebook_ir))
    assert app.config.app_title == "My Title"
    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 2
    assert app.cell_manager.cell_data_at(ids[0]).code.startswith("mo.md")
    assert app.cell_manager.cell_data_at(ids[0]).config.hide_code is True
    assert (
        app.cell_manager.cell_data_at(ids[1]).code == 'print("Hello, World!")'
    )
    assert app.cell_manager.cell_data_at(ids[1]).config.hide_code is False


def test_mystmd_marimo_directives() -> None:
    script = dedent(
        remove_empty_lines(
            """
    ---
    title: "My Title"
    width: full
    header: |
        import os
    pyproject: |
        dependencies = ["polars"]
    ---

    # Notebook

    ````{marimo} python
    :hide-code: true

    print("Hello, World!")
    ````

    ```{marimo} sql
    :query: result
    :engine: engines["primary"]

    SELECT 1
    ```
    """
        )
    )

    notebook_ir = convert_from_md_to_marimo_ir(script)
    app = InternalApp(load_notebook_ir(notebook_ir))

    assert app.config.app_title == "My Title"
    assert app.config.width == "full"
    assert notebook_ir.header is not None
    assert "import os" in notebook_ir.header.value
    assert 'dependencies = ["polars"]' in notebook_ir.header.value

    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 3
    assert app.cell_manager.cell_data_at(ids[0]).code.startswith("mo.md")
    assert app.cell_manager.cell_data_at(ids[1]).config.hide_code is True
    assert (
        app.cell_manager.cell_data_at(ids[1]).code == 'print("Hello, World!")'
    )
    assert "SELECT 1" in app.cell_manager.cell_data_at(ids[2]).code
    assert "result" in app.cell_manager.cell_data_at(ids[2]).code
    assert (
        'engine=engines["primary"]'
        in app.cell_manager.cell_data_at(ids[2]).code
    )


def test_mystmd_marimo_config_directive() -> None:
    config_lines = (
        "```{marimo-config}",
        "---",
        "header: |-",
        "  import os",
        "pyproject: |-",
        '  dependencies = ["polars"]',
        "---",
        "````",
    )
    script_lines = (
        *config_lines,
        "",
        "# Notebook",
        "",
        "```{marimo} python",
        "x = 1",
        "```",
    )
    script = "\n".join(script_lines)

    notebook_ir = convert_from_md_to_marimo_ir(script)
    app = InternalApp(load_notebook_ir(notebook_ir))

    assert notebook_ir.header is not None
    assert "import os" in notebook_ir.header.value
    assert 'dependencies = ["polars"]' in notebook_ir.header.value

    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 2
    assert app.cell_manager.cell_data_at(ids[0]).code.startswith("mo.md")
    assert app.cell_manager.cell_data_at(ids[1]).code == "x = 1"


def test_mystmd_marimo_config_directive_only() -> None:
    script_lines = (
        "```{marimo-config}",
        "---",
        "header: |-",
        "  import os",
        "pyproject: |-",
        '  dependencies = ["polars"]',
        "---",
        "```",
    )
    script = "\n".join(script_lines)

    notebook_ir = convert_from_md_to_marimo_ir(script)

    assert notebook_ir.cells == []
    assert notebook_ir.header is not None
    assert "import os" in notebook_ir.header.value
    assert 'dependencies = ["polars"]' in notebook_ir.header.value


def test_mystmd_indented_marimo_directives() -> None:
    script_lines = (
        "  ```{marimo-config}",
        "---",
        "header: import os",
        "width: full",
        "---",
        "  ```",
        "",
        "   ```{marimo} python",
        "x = 1",
        "   ```",
    )
    notebook_ir = convert_from_md_to_marimo_ir("\n".join(script_lines))
    app = InternalApp(load_notebook_ir(notebook_ir))

    assert app.config.width == "full"
    assert notebook_ir.header is not None
    assert "import os" in notebook_ir.header.value

    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 1
    assert app.cell_manager.cell_data_at(ids[0]).code == "x = 1"


def test_mystmd_literal_directives_in_fenced_example() -> None:
    script_lines = (
        "````markdown",
        "```{marimo-config}",
        "---",
        "width: full",
        "---",
        "```",
        "",
        "```{marimo} python",
        "x = 1",
        "```",
        "````",
    )

    notebook_ir = convert_from_md_to_marimo_ir("\n".join(script_lines))

    assert notebook_ir.header is None
    assert "width" not in notebook_ir.app.options
    assert len(notebook_ir.cells) == 1
    assert "{marimo-config}" in notebook_ir.cells[0].code
    assert "{marimo} python" in notebook_ir.cells[0].code
    assert "x = 1" in notebook_ir.cells[0].code


def test_mystmd_marimo_config_keeps_indented_yaml_delimiters() -> None:
    from marimo._utils import yaml

    script_lines = (
        "```{marimo-config}",
        "---",
        "header: |-",
        "  before",
        "  ---",
        "  after",
        "---",
        "```",
    )

    notebook_ir = convert_from_md_to_marimo_ir("\n".join(script_lines))

    assert notebook_ir.header is not None
    assert (
        yaml.load(notebook_ir.header.value)["header"] == "before\n---\nafter"
    )


def test_mystmd_exported_width_round_trips() -> None:
    notebook = NotebookSerializationV1(
        app=AppInstantiation(options={"width": "full"}),
        cells=[CellDef(name="__", code="x = 1", options={})],
        filename="notebook.myst.md",
    )

    markdown = convert_from_ir_to_markdown(
        notebook, filename="notebook.myst.md", flavor="mystmd"
    )
    round_tripped = convert_from_md_to_marimo_ir(markdown)

    assert "```{marimo-config}" in markdown
    assert "width: full" in markdown
    assert round_tripped.app.options["width"] == "full"


def test_mystmd_marimo_config_directive_reexports() -> None:
    script_lines = (
        "```{marimo-config}",
        "---",
        "header: |-",
        "  import os",
        "pyproject: |-",
        '  dependencies = ["polars"]',
        "---",
        "```",
        "",
        "```{marimo} python",
        "x = 1",
        "```",
    )
    notebook_ir = convert_from_md_to_marimo_ir("\n".join(script_lines))

    markdown = convert_from_ir_to_markdown(
        notebook_ir, filename="notebook.myst.md", flavor="mystmd"
    )

    assert "```{marimo-config}" in markdown
    assert "import os" in markdown
    assert 'dependencies = ["polars"]' in markdown
    assert "```{marimo} python\nx = 1\n```" in markdown


def test_mystmd_exported_config_directive_round_trips() -> None:
    header_lines = (
        "header: |-",
        "  import os",
        "pyproject: |-",
        '  dependencies = ["polars"]',
    )
    notebook = NotebookSerializationV1(
        app=AppInstantiation(options={}),
        cells=[CellDef(name="__", code="x = 1", options={})],
        header=Header(value="\n".join(header_lines)),
        filename="notebook.py",
    )

    markdown = convert_from_ir_to_markdown(
        notebook, filename="notebook.myst.md", flavor="mystmd"
    )
    round_tripped = convert_from_md_to_marimo_ir(markdown)

    assert "```{marimo-config}" in markdown
    assert len(round_tripped.cells) == 1
    assert round_tripped.cells[0].code == "x = 1"
    assert round_tripped.header is not None
    assert "import os" in round_tripped.header.value
    assert 'dependencies = ["polars"]' in round_tripped.header.value


def test_mystmd_exported_config_uses_longer_fence_for_backticks() -> None:
    header = '"""\n# Header\n\n```\ninside\n```\n"""'
    notebook = NotebookSerializationV1(
        app=AppInstantiation(options={}),
        cells=[CellDef(name="__", code="x = 1", options={})],
        header=Header(value=header),
        filename="notebook.py",
    )

    markdown = convert_from_ir_to_markdown(
        notebook, filename="notebook.myst.md", flavor="mystmd"
    )
    round_tripped = convert_from_md_to_marimo_ir(markdown)

    assert "````{marimo-config}" in markdown
    assert len(round_tripped.cells) == 1
    assert round_tripped.cells[0].code == "x = 1"
    assert round_tripped.header is not None
    assert "# Header" in round_tripped.header.value
    assert "inside" in round_tripped.header.value


def test_mystmd_empty_python_cells_round_trip() -> None:
    notebook = NotebookSerializationV1(
        app=AppInstantiation(options={}),
        cells=[CellDef(name="__", code="", options={})],
        filename="notebook.py",
    )

    markdown = convert_from_ir_to_markdown(
        notebook, filename="notebook.myst.md", flavor="mystmd"
    )
    round_tripped = convert_from_md_to_marimo_ir(markdown)

    assert "pass" not in markdown
    assert len(round_tripped.cells) == 1
    assert round_tripped.cells[0].code == ""


def test_markdown_code_cell_attributes_are_unescaped() -> None:
    script_lines = (
        '```python {.marimo name="a&quot;b &amp; &lt;c&gt;"}',
        "x = 1",
        "```",
    )

    notebook_ir = convert_from_md_to_marimo_ir("\n".join(script_lines))

    assert len(notebook_ir.cells) == 1
    assert notebook_ir.cells[0].name == 'a"b & <c>'

    markdown = convert_from_ir_to_markdown(
        notebook_ir, filename="notebook.md", flavor="pymdown"
    )

    assert 'name="a&quot;b &amp; &lt;c&gt;"' in markdown


def test_no_frontmatter() -> None:
    script = dedent(
        remove_empty_lines(
            """
    # My Notebook

    ```python {.marimo}
    print("Hello, World!")
    ```

    **Appendix**
    - This is the end of the notebook
    """
        )
    )
    output = sanitized_version(md_to_py(script))
    snapshot("no-frontmatter.py.txt", output)

    # As python object
    notebook_ir = convert_from_md_to_marimo_ir(script)
    app = InternalApp(load_notebook_ir(notebook_ir))
    # TODO: Ideally extract notebook title.
    # i.e. assert app.config.app_title == "My Notebook"
    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 3


def test_markdown_just_frontmatter() -> None:
    script = dedent(
        remove_empty_lines(
            """
    ---
    title: "My Title"
    description: "My Description"
    tags: ["tag1", "tag2"]
    filters:
    - name: "filter1"
    - name: "filter2"
    ---

    """
        )
    )
    output = sanitized_version(md_to_py(script))
    assert 'app_title="My Title"' in output
    snapshot("frontmatter-only.py.txt", output)

    # As python object
    notebook_ir = convert_from_md_to_marimo_ir(script)
    app = InternalApp(load_notebook_ir(notebook_ir))
    app.cell_manager.ensure_one_cell()
    assert app.config.app_title == "My Title"
    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 1
    assert app.cell_manager.cell_data_at(ids[0]).code == ""


def test_markdown_frontmatter_metadata_roundtrip() -> None:
    """Frontmatter metadata should survive md -> IR -> md roundtrip."""
    script = dedent(
        remove_empty_lines(
            """
    ---
    title: "My Title"
    author: "Marimo Team"
    description: "A notebook description"
    ---

    ```python {.marimo}
    x = 1
    ```
    """
        )
    )

    notebook_ir = convert_from_md_to_marimo_ir(script)
    roundtripped = MarimoConvert.from_ir(notebook_ir).to_markdown()
    assert "author: Marimo Team" in roundtripped
    # Description is preserved but YAML may use folded style (>-)
    from marimo._convert.markdown.to_ir import extract_frontmatter

    meta, _ = extract_frontmatter(roundtripped)
    assert meta["description"] == "A notebook description"


@pytest.mark.requires("duckdb")
def test_markdown_with_sql() -> None:
    script = dedent(
        remove_empty_lines(
            """
    ---
    title: "My Title"
    description: "My Description"
    tags: ["tag1", "tag2"]
    filters:
    - name: "filter1"
    - name: "filter2"
    ---

    # SQL notebook

    ```python {.marimo}
    mem_engine = fn_that_creates_engine("sqlite:///:memory:")
    ```

    ```sql {.marimo query="export" engine="mem_engine" hide_output="true"}
    SELECT * FROM my_table;
    ```

    ```python {.marimo}
    _df = mo.sql("SELECT * FROM export;")
    ```
    """
        )
    )
    output = sanitized_version(md_to_py(script))
    snapshot("sql-notebook.py.txt", output)

    # As python object
    notebook_ir = convert_from_md_to_marimo_ir(script)
    app = InternalApp(load_notebook_ir(notebook_ir))
    assert app.config.app_title == "My Title"
    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 4
    for i in range(4):
        # Unparsables are None
        assert app.cell_manager.cell_data_at(ids[i]).cell is not None
    assert app.cell_manager.cell_data_at(ids[2]).cell.defs == {"export"}
    assert app.cell_manager.cell_data_at(ids[2]).cell.refs == {
        "mem_engine",
        "my_table",
        "mo",
    }
    # hide_output=True => output=False
    assert "False" in app.cell_manager.cell_data_at(ids[2]).cell._cell.code


def test_markdown_empty() -> None:
    assert md_to_py("") == ""

    # As python object
    notebook_ir = convert_from_md_to_marimo_ir("")
    app = InternalApp(load_notebook_ir(notebook_ir))
    app.cell_manager.ensure_one_cell()
    assert app.config.app_title is None
    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 1
    assert app.cell_manager.cell_data_at(ids[0]).code == ""


def test_python_to_md_header() -> None:
    script = dedent(
        remove_empty_lines(
            """
        #!/usr/bin/env python
        import marimo
        __generated_with = "0.0.0"
        app = marimo.App()
        """
        )
    )
    md = convert_from_py_to_md(script)
    assert "#!/usr/bin/env python" in md
    snapshot("has-header.md.txt", md)


def test_python_to_md_code_injection() -> None:
    unsafe_app = dedent(
        remove_empty_lines(
            """
        import marimo
        __generated_with = "0.0.0"
        app = marimo.App()
        @app.cell
        def __():
            import marimo as mo
            return mo,
        @app.cell
        def __(mo):
            mo.md(\"""
                # Code blocks in code blocks
                Output code for Hello World!
                ```python
                print("Hello World")
                ```
                Execute print
                ```python {.marimo}
                print("Hello World")
                ```
            \""")
            return
        @app.cell
        def __(mo):
            mo.md(f\"""
                with f-string too!
                ```python {{.marimo}}
                print("Hello World")
                ```
            \""")
            return
        @app.cell
        def __(mo):
            mo.md(f\"""
                Not markdown
                ```python {{.marimo}}
                print("1 + 1 = {1 + 1}")
                ```
            \""")
            return
        @app.cell
        def __(mo):
            mo.md(\"""
                Nested fence
                ````text
                The guards are
                ```python {.marimo}
                ````
            \""")
            return
        @app.cell
        def __(mo):
            \"""
            ```
            \"""
            return
        @app.cell
        def __(mo):
            mo.md(\"""
                Cross cell injection
                ```python
            \""")
            return
        @app.cell
        def __(mo):
            1 + 1
            return
        def __(mo):
            mo.md(\"""
                ```
            \""")
            return
        @app.cell
        def __():
            # Actual print
            print("Hello World")
            return
        if __name__ == "__main__":
            app.run()
        """
        )
    )
    maybe_unsafe_md = convert_from_py_to_md(unsafe_app).strip()
    maybe_unsafe_py = md_to_py(maybe_unsafe_md).strip()
    snapshot("unsafe-app.py.txt", maybe_unsafe_py)
    snapshot("unsafe-app.md.txt", maybe_unsafe_md)

    # Idempotent even under strange conditions.
    assert convert_from_py_to_md(maybe_unsafe_py).strip() == maybe_unsafe_md

    original_count = len(unsafe_app.split("@app.cell"))
    count = len(maybe_unsafe_py.split("@app.cell"))
    assert original_count == count, (
        "Differing number of cells found,"
        f"injection detected. Expected {original_count} found {count}"
    )


def test_md_to_python_code_injection() -> None:
    script = dedent(
        remove_empty_lines(
            """
    ---
    title: "Casually malicious md"
    ---

    What happens if I just leave a \"""
    " ' ! @ # $ % ^ & * ( ) + = - _ [ ] { } | \\ /

    # Notebook
    <!--
    \\
    ```python {.marimo}
    print("Hello, World!")
    ```
    -->

    ```marimo run convert document.md```

    ```python {.marimo}
    it's an unparsable cell
    ```

    <!-- Actually markdown -->
    ```python {.marimo} `
      print("Hello, World!")

    <!-- Disabled code block -->
    ```python {.marimo disabled="true"}
    1 + 1
    ```

    <!-- Hidden code block -->
    ```python {.marimo hide_code="true"}
    1 + 1
    ```

    <!-- Empty code block -->
    ```python {.marimo}
    ```

    <!-- Improperly nested code block -->
    ```python {.marimo}
    \"""
    ```python {.marimo}
    print("Hello, World!")
    ```
    \"""
    ```

    <!-- Improperly nested code block -->
    ```python {.marimo}
    ````python {.marimo}
    print("Hello, World!")
    ````
    ```

    -->

    <!-- from the notebook, should remain unchanged -->
    ````python {.marimo}
    mo.md(\"""
      This is a markdown cell with an execution block in it
      ```python {.marimo}
      # To ambiguous to convert
      ```
      \""")
    ````

    """
        )
    )

    maybe_unsafe_py = sanitized_version(md_to_py(script).strip())
    maybe_unsafe_md = convert_from_py_to_md(maybe_unsafe_py)

    assert maybe_unsafe_py == sanitized_version(
        md_to_py(maybe_unsafe_md).strip()
    )

    snapshot("unsafe-doc.py.txt", maybe_unsafe_py)
    snapshot("unsafe-doc.md.txt", maybe_unsafe_md)


def remove_empty_lines(s: str) -> str:
    "Just remove the first and last lines if they are empty"
    lines = s.splitlines()
    if not lines[0].strip():
        lines = lines[1:]
    if not lines[-1].strip():
        lines = lines[:-1]
    return "\n".join(lines)
