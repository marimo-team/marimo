# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import json
import sys

from marimo._ast.compiler import compile_cell
from marimo._ast.transformers import NameTransformer
from marimo._cli.convert.utils import (
    generate_from_sources,
    load_external_file,
    markdown_to_marimo,
)
from marimo._runtime.dataflow import DirectedGraph


def fixup_multiple_definitions(sources: list[str]) -> list[str]:
    if sys.version_info < (3, 9):
        # ast.unparse not available in Python 3.8
        return sources

    try:
        cells = [
            compile_cell(source, cell_id=str(i))
            for i, source in enumerate(sources)
        ]
    except SyntaxError:
        return sources

    graph = DirectedGraph()
    for cell in cells:
        graph.register_cell(cell_id=cell.cell_id, cell=cell)

    multiply_defined_names = graph.get_multiply_defined()
    if not multiply_defined_names:
        return sources

    name_transformations = {}
    for name in multiply_defined_names:
        if not graph.get_referring_cells(name):
            name_transformations[name] = (
                "_" + name if not name.startswith("_") else name
            )

    return [
        ast.unparse(
            NameTransformer(name_transformations).visit(ast.parse(source))
        )
        for source in sources
    ]


def convert_from_ipynb(raw_notebook: str) -> str:
    notebook = json.loads(raw_notebook)
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
            source = markdown_to_marimo(source)
        sources.append(source)

    if has_markdown:
        sources.append("import marimo as mo")

    return generate_from_sources(fixup_multiple_definitions(sources))


def convert_from_ipynb_file(file_path: str) -> str:
    raw_notebook = load_external_file(file_path, "ipynb")
    return convert_from_ipynb(raw_notebook)
