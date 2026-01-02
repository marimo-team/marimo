# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _(y):
    x = y
    return (x,)


@app.cell
def _(z):
    y = z
    return (y,)


@app.cell
def _(x):
    z = x
    c = 0
    return (z,)


@app.cell
def _(b):
    a = 0
    del b
    c = 0
    return


app._unparsable_cell(
    r"""

        a =

    """,
    name="_"
)


@app.cell
def _():
    a = 1
    b = 0
    c = 0
    return (b,)


if __name__ == "__main__":
    app.run()
