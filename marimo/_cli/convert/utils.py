# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import urllib.request
from typing import Optional

from marimo._ast import codegen
from marimo._ast.app import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._cli.file_path import get_github_src_url, is_github_src


def load_external_file(file_path: str, ext: str) -> str:
    notebook: str = ""
    if is_github_src(file_path, ext=ext):
        notebook = (
            urllib.request.urlopen(get_github_src_url(file_path))
            .read()
            .decode("utf-8")
        )
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            notebook = f.read()

    return notebook


def markdown_to_marimo(source: str) -> str:
    source = source.replace('"""', '\\"\\"\\"')
    return "\n".join(
        [
            "mo.md(",
            # r-string: a backslash is just a backslash!
            codegen.indent_text('r"""'),
            codegen.indent_text(source),
            codegen.indent_text('"""'),
            ")",
        ]
    )


def generate_from_sources(
    sources: list[str], config: Optional[_AppConfig] = None
) -> str:
    return codegen.generate_filecontents(
        sources,
        ["__" for _ in sources],
        [CellConfig() for _ in range(len(sources))],
        config=config,
    )
