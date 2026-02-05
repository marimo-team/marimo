# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    t = mo.ui.table({"a": [1, 2, 3], "b": [4, 5, 6]})
    return (t,)


@app.cell
def _(t):
    t
    return


if __name__ == "__main__":
    app.run()
