# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import sys
import tempfile
from textwrap import dedent

import pytest

from marimo import __version__
from marimo._cli.convert.markdown import convert_from_md
from marimo._server.export import export_as_md
from marimo._server.export.utils import format_filename_title

# Just a handful of scripts to test
from marimo._tutorials import dataflow, marimo_for_jupyter_users
from tests.mocks import snapshotter

modules = {
    "marimo_for_jupyter_users": marimo_for_jupyter_users,
    "dataflow": dataflow,
}

DIR_PATH = os.path.dirname(os.path.realpath(__file__))

snapshot = snapshotter(__file__)


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
            output = export_as_md(tempfile_name)[0]
    finally:
        os.remove(tempfile_name)

    title = format_filename_title(tempfile_name)
    output = output.replace(title, "Test Notebook")
    return sanitized_version(output)


# Regarding windows skip: This should be fine, as less complex cases are
# captured by test_markdown_frontmatter. Here, snapshotting fails in windows
# due to emojis in the tutorials :(
@pytest.mark.skipif(
    sys.platform == "win32", reason="Failing on Windows CI due to emojis"
)
def test_markdown_snapshots() -> None:
    for name, mod in modules.items():
        output = sanitized_version(export_as_md(mod.__file__)[0])
        snapshot(f"{name}.md.txt", output)


# Windows does not encode emojis correctly for md -> python
@pytest.mark.skipif(
    sys.platform == "win32", reason="Failing on Windows CI due to emojis"
)
def test_idempotent_markdown_to_marimo() -> None:
    for script in modules.keys():
        with open(DIR_PATH + f"/snapshots/{script}.md.txt") as f:
            md = f.read()
        python_source = sanitized_version(convert_from_md(md))
        assert convert_from_py(python_source) == md.strip()


def test_markdown_frontmatter() -> None:
    script = dedent(
        """
    ---
    title: "My Title"
    description: "My Description"
    tags: ["tag1", "tag2"]
    filters:
    - name: "filter1"
    - name: "filter2"
    ---

    # Notebook

    ```{.python.marimo}
    print("Hello, World!")
    ```
    """[1:]
    )
    output = sanitized_version(convert_from_md(script))
    assert 'app_title="My Title"' in output
    snapshot("frontmatter-test.py.txt", output)


def test_markdown_just_frontmatter() -> None:
    script = dedent(
        """
    ---
    title: "My Title"
    description: "My Description"
    tags: ["tag1", "tag2"]
    filters:
    - name: "filter1"
    - name: "filter2"
    ---
    """[1:]
    )
    output = sanitized_version(convert_from_md(script))
    assert 'app_title="My Title"' in output


def test_markdown_empty() -> None:
    assert convert_from_md("") == ""


def test_python_to_md_code_injection() -> None:
    unsafe_app = dedent(
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
                ```{python}
                print("Hello World")
                ```
            \""")
            return
        @app.cell
        def __(mo):
            mo.md(f\"""
                with f-string too!
                ```{{python}}
                print("Hello World")
                ```
            \""")
            return
        @app.cell
        def __(mo):
            mo.md(f\"""
                Not markdown
                ```{{python}}
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
                ```{python}
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
        """[1:]
    )
    maybe_unsafe_md = convert_from_py(unsafe_app).strip()
    print("-----------------------------------------------")
    maybe_unsafe_py = sanitized_version(
        convert_from_md(maybe_unsafe_md).strip()
    )
    snapshot("unsafe-app.py.txt", maybe_unsafe_py)
    # print(maybe_unsafe_py)
    snapshot("unsafe-app.md.txt", maybe_unsafe_md)
    # print(maybe_unsafe_md)

    # Idempotent even under strange conditions.
    assert convert_from_py(maybe_unsafe_py).strip() == maybe_unsafe_md

    original_count = len(unsafe_app.split("@app.cell"))
    count = len(maybe_unsafe_py.split("@app.cell"))
    assert original_count == count, (
        "Differing number of cells found,"
        f"injection detected. Expected {original_count} found {count}"
    )


def test_md_to_python_code_injection() -> None:
    script = dedent(
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
    """[1:]
    )

    maybe_unsafe_py = sanitized_version(convert_from_md(script).strip())
    print(maybe_unsafe_py)
    maybe_unsafe_md = convert_from_py(maybe_unsafe_py)
    print(maybe_unsafe_md)

    # Idempotent even under strange conditions.
    assert maybe_unsafe_py == sanitized_version(
        convert_from_md(maybe_unsafe_md).strip()
    )
    # raise NotImplementedError("This test is not yet implemented.")
