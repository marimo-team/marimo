# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Innermost
    """)


@app.cell
def _(mo):
    x = mo.ui.number(1, 10)
    return (x,)


@app.cell
def _(x):
    x


@app.cell
def _(mo):
    y = mo.ui.number(1, 10)
    return (y,)


@app.cell
def _(y):
    y


@app.cell
def _(x, y):
    x.value + y.value


if __name__ == "__main__":
    app.run()
