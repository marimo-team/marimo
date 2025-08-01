# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable

from marimo import _loggers
from marimo._ast.app import App, InternalApp
from marimo._ast.compiler import toplevel_cell_factory
from marimo._ast.names import (
    SELF_CELL_NAME,
    SETUP_CELL_NAME,
    TOPLEVEL_CELL_PREFIX,
)
from marimo._ast.toplevel import TopLevelExtraction
from marimo._runtime.dataflow import DirectedGraph
from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def graph_from_app(fn: Callable[..., Any], app: App) -> DirectedGraph:
    cell_manager = app._cell_manager
    extraction = TopLevelExtraction.from_app(InternalApp(app))
    graph = DirectedGraph()
    for cell_id, cell in cell_manager.valid_cells():
        name = cell.name.strip(TOPLEVEL_CELL_PREFIX)
        if name in extraction.toplevel or name == SETUP_CELL_NAME:
            graph.register_cell(cell_id, cell._cell)

    # We finally have to register the wrapped function itself.
    cell_id = CellId_t(SELF_CELL_NAME)
    cell = toplevel_cell_factory(fn, cell_id)
    graph.register_cell(cell_id, cell._cell)
    return graph


def graph_from_scope(
    fn: Callable[..., Any], scope: dict[str, Any]
) -> DirectedGraph:
    app = scope.get("app", None)
    if not isinstance(app, App):
        LOGGER.warning(
            "The scope does not contain a valid 'app' instance. "
            "marimo bevehavior may be undefined."
        )
        return DirectedGraph()

    return graph_from_app(fn, app)
