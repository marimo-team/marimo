# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.19.11"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Basic column vector (1D matrix)
    """)
    return


@app.cell
def _(mo):
    col = mo.ui.matrix([1, 2, 3], precision=2, label="Column vector")
    col
    return (col,)


@app.cell
def _(col):
    col.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## With bounds and step
    """)
    return


@app.cell
def _(mo):
    bounded = mo.ui.matrix(
        [0, 0, 0, 0],
        min_value=-5,
        max_value=5,
        step=0.25,
        precision=2,
        label="Bounded ([-5, 5], step=0.25)",
    )
    bounded
    return (bounded,)


@app.cell
def _(bounded):
    bounded.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## With row labels
    """)
    return


@app.cell
def _(mo):
    labeled = mo.ui.matrix(
        [1.0, 0.5, 0.0],
        row_labels=["x", "y", "z"],
        step=0.1,
        precision=1,
        label="$v$",
    )
    labeled
    return (labeled,)


@app.cell
def _(labeled):
    labeled.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## NumPy interop
    """)
    return


@app.cell
def _(mo):
    import numpy as np

    np_vec = mo.ui.matrix(
        np.zeros(5),
        step=0.1,
        precision=1,
        label=r"$\vec{0}$",
    )
    np_vec
    return np, np_vec


@app.cell
def _(np, np_vec):
    np.asarray(np_vec.value)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Scientific notation
    """)
    return


@app.cell
def _(mo):
    sci = mo.ui.matrix(
        [0.00153, 1234567, 1e-8, -0.042],
        scientific=True,
        precision=2,
        step=1e-4,
        label="Scientific notation",
    )
    sci
    return (sci,)


@app.cell
def _(sci):
    sci.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Debounce
    """)
    return


@app.cell
def _(mo):
    db = mo.ui.matrix(
        [1, 2, 3],
        precision=2,
        debounce=True,
        label="Debounced",
    )
    db
    return (db,)


@app.cell
def _(db):
    db.value
    return


if __name__ == "__main__":
    app.run()
