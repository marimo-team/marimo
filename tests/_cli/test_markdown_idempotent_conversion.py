# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile

from marimo import __version__
from marimo._cli.convert.markdown import convert_from_md
from marimo._server.export import export_as_md
from marimo._server.export.utils import format_filename_title

DIR_PATH = os.path.dirname(os.path.realpath(__file__))

scripts = [
    "dataflow",
    "fileformat",
    "intro",
    "layout",
    "marimo_for_jupyter_users",
    "plots",
    "ui",
]


def convert_from_py(py: str, script: str) -> str:
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

    output = output.replace(__version__, "0.0.0")
    output = output.replace(
        format_filename_title(tempfile_name), format_filename_title(script)
    )
    return output


def test_idempotent_markdown_to_marimo() -> None:
    for script in scripts:
        with open(DIR_PATH + f"/markdown_data/{script}.md.txt") as f:
            md = f.read()
        with open(DIR_PATH + f"/markdown_data/{script}.py.txt") as f:
            py = f.read()
        md_output = convert_from_md(md)
        md_output = md_output.replace(__version__, "0.0.0")
        assert md_output == py.strip()
        assert convert_from_py(md_output, script) == md.strip()
