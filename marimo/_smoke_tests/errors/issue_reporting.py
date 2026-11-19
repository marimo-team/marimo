# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.md(r"""
    # Marimo bug reporting

    Run all cells in edit mode. The synthetic `MarimoBugError` and the duplicate graph
    node should offer **Report a marimo bug**; the two user errors should not.

    Open the report and check the environment, traceback, and error/code toggles.
    """)
    return


@app.cell
def marimo_bug():
    from marimo._core.errors import MarimoBugError as _MarimoBugError

    raise _MarimoBugError("Synthetic marimo error")
    return


@app.cell
def duplicate_graph_node():
    from marimo._ast.compiler import compile_cell
    from marimo._runtime.dataflow.topology import MutableGraphTopology
    from marimo._types.ids import CellId_t

    _graph = MutableGraphTopology()
    _id = CellId_t("demo")
    _cell = compile_cell("answer = 42", cell_id=_id)
    _graph.add_node(_id, _cell)
    _graph.add_node(_id, _cell)
    return


@app.cell
def user_value_error():
    raise ValueError("User error")
    return


@app.cell
def user_defined_marimo_bug_error():
    class MarimoBugError(RuntimeError):
        pass

    raise MarimoBugError("User-defined MarimoBugError")
    return


if __name__ == "__main__":
    app.run()
