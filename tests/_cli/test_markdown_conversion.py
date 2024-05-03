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
    print(script)
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
    script = ""
    with pytest.raises(ValueError):
        convert_from_md(script)
