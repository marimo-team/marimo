# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import urllib.request
from typing import Any

from marimo._ast import codegen
from marimo._ast.cell import CellConfig
from marimo._cli.file_path import get_github_src_url, is_github_src


def convert_from_path(ipynb_path: str) -> str:
    if is_github_src(ipynb_path, ext=".ipynb"):
        notebook = json.loads(
            urllib.request.urlopen(get_github_src_url(ipynb_path))
            .read()
            .decode("utf-8")
        )
    else:
        with open(ipynb_path, "r", encoding="utf-8") as f:
            notebook = json.loads(f.read())

    return convert(notebook)


def convert(notebook: dict[str, Any]) -> str:
    sources = []
    has_markdown = False
    for cell in notebook["cells"]:
        source = (
            cell["source"]
            if isinstance(cell["source"], str)
            else "".join(cell["source"])
        )
        if cell["cell_type"] == "markdown":
            has_markdown = True
            source = source.replace('"""', '\\"\\"\\"')
            source = "\n".join(
                [
                    "mo.md(",
                    # r-string: a backslash is just a backslash!
                    codegen.indent_text('r"""'),
                    codegen.indent_text(source),
                    codegen.indent_text('"""'),
                    ")",
                ]
            )
        sources.append(source)
    if has_markdown:
        sources.append("import marimo as mo")

    return codegen.generate_filecontents(
        sources,
        ["_" for _ in sources],
        [CellConfig() for _ in range(len(sources))],
    )
