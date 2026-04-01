# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.app import InternalApp
from marimo._ast.load import load_notebook_ir
from marimo._runtime.dataflow import topological_sort
from marimo._schemas.serialization import NotebookSerialization
from marimo._version import __version__


def _header_for_script(ir: NotebookSerialization) -> str:
    """Extract a Python script-appropriate header from IR.

    Python-origin notebooks store raw header text (PEP 723 block, copyright
    comments) in ir.header.value. Markdown-origin notebooks store YAML
    frontmatter, which must be parsed to recover the pyproject/header fields.
    """
    value = (ir.header.value if ir.header else None) or ""
    if not value:
        return ""

    # Python-origin: all comment lines parse as YAML comments → None
    # Markdown-origin: YAML dict with possible "pyproject"/"header" keys
    try:
        import yaml

        frontmatter = yaml.safe_load(value)
        if isinstance(frontmatter, dict) and (
            "pyproject" in frontmatter or "header" in frontmatter
        ):
            from marimo._utils.inline_script_metadata import (
                get_headers_from_frontmatter,
            )

            headers = get_headers_from_frontmatter(frontmatter)
            return headers.get("pyproject") or headers.get("header") or ""
    except Exception:
        pass

    return value


def convert_from_ir_to_script(ir: NotebookSerialization) -> str:
    """Convert a notebook IR to a flat Python script with ``# %%`` cell separators."""
    app = InternalApp(load_notebook_ir(ir))

    # Check if any code is async, if so, raise an error
    for cell in app.cell_manager.cells():
        if not cell:
            continue
        if cell._is_coroutine:
            from click import ClickException

            raise ClickException(
                "Cannot export a notebook with async code to a flat script"
            )

    graph = app.graph
    header = _header_for_script(ir)
    codes: list[str] = [
        "# %%\n" + graph.cells[cid].code
        for cid in topological_sort(graph, graph.cells.keys())
    ]
    return f'{header}\n__generated_with = "{__version__}"\n\n' + "\n\n".join(
        codes
    )
