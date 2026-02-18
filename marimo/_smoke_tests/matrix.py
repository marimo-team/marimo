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
    ## Basic matrix (2x2 identity)
    """)
    return


@app.cell
def _(mo):
    identity = mo.ui.matrix([[1, 0], [0, 1]], label="Identity")
    identity
    return (identity,)


@app.cell
def _(identity):
    identity.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## With bounds, step, and precision
    """)
    return


@app.cell
def _(mo):
    bounded = mo.ui.matrix(
        [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
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
    ## With row and column labels
    """)
    return


@app.cell
def _(mo):
    labeled = mo.ui.matrix(
        [[1, 2, 3], [4, 5, 6]],
        row_labels=["x", "y"],
        column_labels=["a", "b", "c"],
        label="Labeled matrix",
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
    ## Symmetric mode (square matrix)
    """)
    return


@app.cell
def _(mo):
    sym = mo.ui.matrix(
        [[1, 0.5, 0], [0.5, 1, 0.3], [0, 0.3, 1]],
        min_value=-1,
        max_value=1,
        step=0.1,
        precision=1,
        symmetric=True,
        label="Symmetric (drag [i,j] to also update [j,i])",
    )
    sym
    return (sym,)


@app.cell
def _(sym):
    sym.value
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Per-element disabled mask
    """)
    return


@app.cell
def _(mo):
    masked = mo.ui.matrix(
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        disabled=[
            [True, False, False],
            [False, True, False],
            [False, False, True],
        ],
        label="Diagonal locked",
    )
    masked
    return (masked,)


@app.cell
def _(masked):
    masked.value
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

    np_mat = mo.ui.matrix(
        np.eye(3),
        step=0.1,
        precision=1,
        label="$X$",
    )
    np_mat
    return np, np_mat


@app.cell
def _(np, np_mat):
    arr = np.asarray(np_mat.value)
    arr
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## NumPy arrays for bounds and step
    """)
    return


@app.cell
def _(mo, np):
    np_bounds = mo.ui.matrix(
        np.zeros((3, 3)),
        min_value=np.full((3, 3), -10.0),
        max_value=np.full((3, 3), 10.0),
        step=np.full((3, 3), 0.5),
        precision=1,
        label="np bounds and step",
    )
    np_bounds
    return (np_bounds,)


@app.cell
def _(np, np_bounds):
    np.asarray(np_bounds.value)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## NumPy per-element step (varies by cell)
    """)
    return


@app.cell
def _(mo, np):
    step_matrix = np.array([[0.1, 0.5, 1.0], [1.0, 0.5, 0.1], [0.01, 0.01, 0.01]])
    varying_step = mo.ui.matrix(
        np.zeros((3, 3)),
        step=step_matrix,
        precision=2,
        label="Per-element step",
        column_labels=["step=col", "step=mid", "step=fine"],
    )
    varying_step
    return (varying_step,)


@app.cell
def _(np, varying_step):
    np.asarray(varying_step.value)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## NumPy disabled mask
    """)
    return


@app.cell
def _(mo, np):
    mask = np.eye(4, dtype=bool)
    np_disabled = mo.ui.matrix(
        np.arange(16, dtype=float).reshape(4, 4),
        disabled=mask,
        precision=0,
        label=r"$\text{diag}(0, 5, 10, 15) + X$",
    )
    np_disabled
    return (np_disabled,)


@app.cell
def _(np, np_disabled):
    np.asarray(np_disabled.value)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## NumPy: asymmetric bounds (different per cell)
    """)
    return


@app.cell
def _(mo, np):
    mins = np.array([[0, -5], [-10, -1]])
    maxs = np.array([[10, 5], [10, 1]])
    asym = mo.ui.matrix(
        np.array([[5.0, 0.0], [0.0, 0.0]]),
        min_value=mins,
        max_value=maxs,
        step=0.5,
        precision=1,
        row_labels=["row0", "row1"],
        column_labels=["[0,10]|[-5,5]", "[-10,10]|[-1,1]"],
        label="Per-cell bounds from numpy",
    )
    asym
    return (asym,)


@app.cell
def _(asym, np):
    np.asarray(asym.value)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Round-trip: numpy in, numpy out
    """)
    return


@app.cell
def _(mo, np):
    original = np.random.default_rng(42).uniform(-1, 1, size=(3, 3)).round(2)
    roundtrip = mo.ui.matrix(
        original,
        precision=2,
        step=0.01,
        label="Random matrix (edit and check below)",
    )
    roundtrip
    return original, roundtrip


@app.cell
def _(np, original, roundtrip):
    current = np.asarray(roundtrip.value)
    mo_result = {
        "original": original,
        "current": current,
        "changed": not np.array_equal(original, current),
        "dtype": current.dtype,
        "shape": current.shape,
    }
    mo_result
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
        [[0.00153, 1234567], [1e-8, -0.042]],
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


if __name__ == "__main__":
    app.run()
