# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    get_v, set_v = mo.state(True)
    get_v2, set_v2 = mo.state(True)
    return get_v, get_v2, set_v, set_v2


@app.cell
def _(get_v, get_v2):
    [get_v(), get_v2()]
    return


@app.cell
def _(get_v, mo, set_v):
    x = mo.ui.checkbox(get_v(), on_change=set_v)
    x
    return


@app.cell
def _(get_v, mo, set_v):
    y = mo.ui.checkbox(get_v(), on_change=set_v)
    y
    return


@app.cell
def _(get_v2, mo, set_v2):
    mo.ui.checkbox(get_v2(), on_change=set_v2)
    return


@app.cell
def _(get_v2, mo, set_v2):
    mo.ui.checkbox(get_v2(), on_change=set_v2)
    return


if __name__ == "__main__":
    app.run()
