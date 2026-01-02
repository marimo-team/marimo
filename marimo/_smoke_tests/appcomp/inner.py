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
    mo.md("# Innermost")
    return


@app.cell
def _():
    x_initial_value = 1
    return (x_initial_value,)

@app.cell
def _(mo, x_initial_value):
    x = mo.ui.number(x_initial_value, 10)
    return (x,)


@app.cell
def _(x):
    x
    return


@app.cell
def _(mo):
    y = mo.ui.number(1, 10)
    return (y,)


@app.cell
def _(y):
    y
    return

@app.cell
def _(x, y):
    x.value + y.value
    return


if __name__ == "__main__":
    app.run()
