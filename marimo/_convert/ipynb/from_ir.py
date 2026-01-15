# Copyright 2026 Marimo. All rights reserved.
"""Export marimo notebooks to Jupyter ipynb format."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from marimo._ast.cell import Cell, CellConfig
from marimo._ast.errors import CycleError, MultipleDefinitionError
from marimo._ast.names import is_internal_cell_name
from marimo._convert.common.utils import get_markdown_from_cell
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime import dataflow

if TYPE_CHECKING:
    from nbformat.notebooknode import NotebookNode  # type: ignore

    from marimo._ast.app import InternalApp


def convert_from_ir_to_ipynb(
    app: InternalApp,
    *,
    sort_mode: Literal["top-down", "topological"],
) -> str:
    """Export notebook as .ipynb without outputs.

    Args:
        app: The internal app to export
        sort_mode: How to order cells - "top-down" preserves notebook order,
                   "topological" orders by dependencies

    Returns:
        JSON string of the .ipynb notebook
    """
    DependencyManager.nbformat.require("to convert marimo notebooks to ipynb")
    import nbformat  # type: ignore[import-not-found]

    notebook = nbformat.v4.new_notebook()  # type: ignore[no-untyped-call]
    notebook["cells"] = []

    # Determine cell order based on sort_mode
    if sort_mode == "top-down":
        cell_data_list = list(app.cell_manager.cell_data())
    else:
        # Topological sort - try to sort, fall back to top-down on cycle
        try:
            graph = app.graph
            sorted_ids = dataflow.topological_sort(graph, graph.cells.keys())
            # Build cell_data list in topological order
            cell_data_list = [
                app.cell_manager.cell_data_at(cid)
                for cid in sorted_ids
                if cid in graph.cells
            ]
        except (CycleError, MultipleDefinitionError):
            # Fall back to top-down order if graph is invalid
            cell_data_list = list(app.cell_manager.cell_data())

    for cell_data in cell_data_list:
        cid = cell_data.cell_id

        notebook_cell = _create_ipynb_cell(
            cell_id=cid,
            code=cell_data.code,
            name=cell_data.name,
            config=cell_data.config,
            cell=cell_data.cell,
            outputs=[],
        )
        notebook["cells"].append(notebook_cell)

    stream = io.StringIO()
    nbformat.write(notebook, stream)  # type: ignore[no-untyped-call]
    stream.seek(0)
    return stream.read()


def _create_ipynb_cell(
    cell_id: str,
    code: str,
    name: str,
    config: CellConfig,
    cell: Optional[Cell],
    outputs: list[NotebookNode],
) -> NotebookNode:
    """Create an ipynb cell with metadata.

    Args:
        cell_id: The cell's unique identifier
        code: The cell's source code
        name: The cell's name
        config: The cell's configuration
        cell: Optional Cell object for markdown detection
        outputs: List of cell outputs (ignored for markdown cells)
    """
    import nbformat

    # Try to extract markdown if we have a valid Cell
    if cell is not None:
        markdown_string = get_markdown_from_cell(cell, code)
        if markdown_string is not None:
            node = cast(
                nbformat.NotebookNode,
                nbformat.v4.new_markdown_cell(markdown_string, id=cell_id),  # type: ignore[no-untyped-call]
            )
            _add_marimo_metadata(node, name, config)
            return node

    node = cast(
        nbformat.NotebookNode,
        nbformat.v4.new_code_cell(code, id=cell_id),  # type: ignore[no-untyped-call]
    )
    if outputs:
        node.outputs = outputs
    _add_marimo_metadata(node, name, config)
    return node


def _add_marimo_metadata(
    node: NotebookNode, name: str, config: CellConfig
) -> None:
    """Add marimo-specific metadata to a notebook cell."""
    marimo_metadata: dict[str, Any] = {}
    if config.is_different_from_default():
        marimo_metadata["config"] = config.asdict_without_defaults()
    if not is_internal_cell_name(name):
        marimo_metadata["name"] = name
    if marimo_metadata:
        node["metadata"]["marimo"] = marimo_metadata
