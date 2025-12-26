# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable

from marimo import _loggers
from marimo._ast.app import App, InternalApp
from marimo._ast.names import (
    SETUP_CELL_NAME,
    TOPLEVEL_CELL_PREFIX,
)
from marimo._ast.toplevel import TopLevelExtraction
from marimo._runtime.dataflow import DirectedGraph
from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def get_app_from_scope(scope: dict[str, Any]) -> App | None:
    app = scope.get("app", None)
    if not isinstance(app, App):
        LOGGER.warning(
            "The scope does not contain a valid 'app' instance. "
            "marimo behavior may be undefined."
        )
        return None

    return app


def graph_from_app(app: App) -> DirectedGraph:
    cell_manager = app._cell_manager
    extraction = TopLevelExtraction.from_app(InternalApp(app))
    graph = DirectedGraph()
    for cell_id, cell in cell_manager.valid_cells():
        name = cell.name.strip(TOPLEVEL_CELL_PREFIX)
        if name in extraction.toplevel or name == SETUP_CELL_NAME:
            graph.register_cell(cell_id, cell._cell)
    return graph


def graph_from_scope(scope: dict[str, Any]) -> DirectedGraph:
    app = get_app_from_scope(scope)
    if app is None:
        return DirectedGraph()
    return graph_from_app(app)


def get_cell_id_from_scope(
    fn: Callable[..., Any], scope: dict[str, Any]
) -> CellId_t:
    app = get_app_from_scope(scope)
    if app is None:
        return CellId_t("")
    maybe_cell = app._cell_manager.get_cell_data_by_name(fn.__name__)
    if maybe_cell is None:
        return CellId_t("")
    return maybe_cell.cell_id
