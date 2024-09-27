# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._ast import codegen
from marimo._ast.app import _AppConfig
from marimo._ast.cell import CellConfig


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
    """
    Given a list of Python source code,
    generate the marimo file contents.
    """
    return codegen.generate_filecontents(
        sources,
        ["__" for _ in sources],
        [CellConfig() for _ in range(len(sources))],
        config=config,
    )
