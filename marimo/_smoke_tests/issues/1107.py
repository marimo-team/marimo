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
    v = mo.ui.number(value=0, start=-10, stop=10)
    v
    return (v,)


@app.cell
def _(v):
    v.value
    return


if __name__ == "__main__":
    app.run()
