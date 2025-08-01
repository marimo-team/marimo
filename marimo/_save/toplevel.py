from marimo._ast.app import App, InternalApp
from marimo._ast.toplevel import TopLevelExtraction
from marimo._ast.compiler import toplevel_cell_factory
from marimo._runtime.dataflow import DirectedGraph

from typing import Any


def graph_from_scope(fn, scope: dict[str, Any]) -> DirectedGraph:
    """
    Generate a graph representation from a given scope dictionary.

    Args:
        scope (dict[str, Any]): A dictionary representing the scope.

    Returns:
        str: A string representation of the graph.
    """

    app = scope.get("app", None)
    if not isinstance(app, App):
        # Warn and return an empty graph
        # warning.warn(
        #     "The scope does not contain a valid 'app' instance. Returning an empty graph."
        # )
        return DirectedGraph()

    cell_manager = app._cell_manager
    extraction = TopLevelExtraction.from_app(InternalApp(app))
    graph = DirectedGraph()
    for cell_id, cell in cell_manager.valid_cells():
        name = cell.name.strip("*")
        if name in extraction.toplevel or name == "setup":
            graph.register_cell(cell_id, cell._cell)

    # We finally have to register the wrapped function itself.
    cell_id = "self"
    cell = toplevel_cell_factory(fn, cell_id)
    graph.register_cell(cell_id, cell._cell)
    return graph
