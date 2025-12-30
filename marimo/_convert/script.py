# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast import codegen
from marimo._ast.app import InternalApp
from marimo._ast.load import load_notebook_ir
from marimo._runtime.dataflow import topological_sort
from marimo._schemas.serialization import NotebookSerialization
from marimo._version import __version__


def convert_from_ir_to_script(ir: NotebookSerialization) -> str:
    filename = ir.filename or "notebook.py"
    app = InternalApp(load_notebook_ir(ir))

    # Check if any code is async, if so, raise an error
    for cell in app.cell_manager.cells():
        if not cell:
            continue
        if cell._is_coroutine:
            from click import UsageError

            raise UsageError(
                "Cannot export a notebook with async code to a flat script"
            )

    graph = app.graph
    header = codegen.get_header_comments(filename) or ""
    codes: list[str] = [
        "# %%\n" + graph.cells[cid].code
        for cid in topological_sort(graph, graph.cells.keys())
    ]
    return f'{header}\n__generated_with = "{__version__}"\n\n' + "\n\n".join(
        codes
    )
