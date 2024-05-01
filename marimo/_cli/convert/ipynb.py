# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json

from marimo._cli.convert.utils import (
    generate_from_sources,
    load_external_file,
    markdown_to_marimo,
)


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

    return generate_from_sources(sources)


def convert_from_ipynb_file(file_path: str) -> str:
    raw_notebook = load_external_file(file_path, "ipynb")
    return convert_from_ipynb(raw_notebook)
