# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import re
import sys
import tempfile
from textwrap import dedent

import pytest

from marimo import __version__
from marimo._ast.app import InternalApp
from marimo._convert.converters import MarimoConvert
from marimo._convert.markdown.markdown import convert_from_md_to_app
from marimo._server.export import export_as_md
from marimo._server.export.utils import format_filename_title

# Just a handful of scripts to test
from marimo._tutorials import dataflow, for_jupyter_users, sql
from marimo._utils.marimo_path import MarimoPath
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


def convert_from_py(py: str) -> str:
    # Needs to be a .py for export to be invoked.
    tempfile_name = ""
    output = ""
    try:
        # in windows, can't re-open an open named temporary file, hence
        # delete=False and manual clean up
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            tempfile_name = f.name
            f.write(py)
            f.seek(0)
            output = export_as_md(MarimoPath(tempfile_name)).contents
    finally:
        os.remove(tempfile_name)

    title = format_filename_title(tempfile_name)
    output = re.sub(rf"'?{title}'?", "Test Notebook", output)
    return sanitized_version(output)


# Regarding windows skip: This should be fine, as less complex cases are
# captured by test_markdown_frontmatter. Here, snapshotting fails in windows
# due to emojis in the tutorials :(
@pytest.mark.skipif(
    sys.platform == "win32", reason="Failing on Windows CI due to emojis"
)
def test_markdown_snapshots() -> None:
    for name, mod in modules.items():
        output = export_as_md(MarimoPath(mod.__file__)).contents
        snapshot(f"{name}.md.txt", output)


# Windows does not encode emojis correctly for md -> python
@pytest.mark.skipif(
    sys.platform == "win32", reason="Failing on Windows CI due to emojis"
)
def test_idempotent_markdown_to_marimo() -> None:
    for script in modules.keys():
        with open(DIR_PATH + f"/snapshots/{script}.md.txt") as f:
            md = f.read()
        python_source = sanitized_version(md_to_py(md))
        assert convert_from_py(python_source) == md.strip()


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
    app = InternalApp(convert_from_md_to_app(script))
    assert app.config.app_title == "My Title"
    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 2
    assert app.cell_manager.cell_data_at(ids[0]).code.startswith("mo.md")
    assert app.cell_manager.cell_data_at(ids[0]).config.hide_code is True
    assert (
        app.cell_manager.cell_data_at(ids[1]).code == 'print("Hello, World!")'
    )
    assert app.cell_manager.cell_data_at(ids[1]).config.hide_code is False


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
    app = InternalApp(convert_from_md_to_app(script))
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
    app = InternalApp(convert_from_md_to_app(script))
    assert app.config.app_title == "My Title"
    ids = list(app.cell_manager.cell_ids())
    assert len(ids) == 1
    assert app.cell_manager.cell_data_at(ids[0]).code == ""


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
    app = InternalApp(convert_from_md_to_app(script))
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
    app = InternalApp(convert_from_md_to_app(""))
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
    md = convert_from_py(script)
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
    maybe_unsafe_md = convert_from_py(unsafe_app).strip()
    maybe_unsafe_py = md_to_py(maybe_unsafe_md).strip()
    snapshot("unsafe-app.py.txt", maybe_unsafe_py)
    snapshot("unsafe-app.md.txt", maybe_unsafe_md)

    # Idempotent even under strange conditions.
    assert convert_from_py(maybe_unsafe_py).strip() == maybe_unsafe_md

    original_count = len(unsafe_app.split("@app.cell"))
    count = len(maybe_unsafe_py.split("@app.cell"))
    assert original_count == count, (
        "Differing number of cells found,"
        f"injection detected. Expected {original_count} found {count}"
    )


def test_old_md_to_python_code_injection() -> None:
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
    ```{.python.marimo}
    print("Hello, World!")
    ```
    -->

    ```marimo run convert document.md```

    ```{python}
    it's an unparsable cell
    ```

    <!-- Actually markdown -->
    ```{python} `
      print("Hello, World!")

    <!-- Disabled code block -->
    ```{python disabled="true"}
    1 + 1
    ```

    <!-- Hidden code block -->
    ```{python hide_code="true"}
    1 + 1
    ```

    <!-- Empty code block -->
    ```{python}
    ```

    <!-- Improperly nested code block -->
    ```{python}
    \"""
    ```{python}
    print("Hello, World!")
    ```
    \"""
    ```

    <!-- Improperly nested code block -->
    ```{python}
    ````{python}
    print("Hello, World!")
    ````
    ```

    -->

    <!-- from the notebook, should remain unchanged -->
    ````{.python.marimo}
    mo.md(\"""
      This is a markdown cell with an execution block in it
      ```{python}
      # To ambiguous to convert
      ```
      \""")
    ````

    """
        )
    )

    maybe_unsafe_py = sanitized_version(md_to_py(script).strip())
    assert "Casually malicious md" in maybe_unsafe_py

    maybe_unsafe_md = convert_from_py(maybe_unsafe_py)
    assert "Casually malicious md" in maybe_unsafe_md

    # Idempotent even under strange conditions.
    assert maybe_unsafe_py == sanitized_version(
        md_to_py(maybe_unsafe_md).strip()
    )

    snapshot("unsafe-doc-old.py.txt", maybe_unsafe_py)
    snapshot("unsafe-doc-old.md.txt", maybe_unsafe_md)


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
    maybe_unsafe_md = convert_from_py(maybe_unsafe_py)

    # Idempotent even under strange conditions.
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
