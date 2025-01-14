# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._ast import codegen
from marimo._ast.app import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._ast.names import DEFAULT_CELL_NAME


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
    *,
    sources: list[str],
    config: Optional[_AppConfig] = None,
    header_comments: Optional[str] = None,
    cell_configs: Optional[list[CellConfig]] = None,
) -> str:
    """
    Given a list of Python source code,
    generate the marimo file contents.
    """
    if cell_configs is None:
        cell_configs = [CellConfig() for _ in range(len(sources))]
    else:
        assert len(cell_configs) == len(sources), (
            "cell_configs must be the same length as sources"
        )

    return codegen.generate_filecontents(
        sources,
        [DEFAULT_CELL_NAME for _ in sources],
        cell_configs,
        config=config,
        header_comments=header_comments,
    )
