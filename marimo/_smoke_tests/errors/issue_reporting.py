# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.md(r"""
    # Internal error reporting

    Run all cells in edit mode. Marimo's error should offer **Report a marimo bug**;
    the two user errors should not. The duplicate graph node also offers it on #11526.

    Open the report and check the environment, traceback, and error/code toggles.
    """)
    return


@app.cell
def marimo_internal_error():
    from marimo._core.errors import InternalError as _MarimoInternalError

    raise _MarimoInternalError("Synthetic marimo error")
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
def user_internal_error():
    class InternalError(RuntimeError):
        pass

    raise InternalError("User-defined InternalError")
    return


if __name__ == "__main__":
    app.run()
