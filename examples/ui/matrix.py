import marimo

__generated_with = "0.19.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import numpy as np

    return mo, np


@app.cell
def _(mo):
    matrix = mo.ui.matrix(
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        min_value=-5,
        max_value=10,
        step=0.001,
        precision=3,
        scientific=True,
        label="$I$",
    )
    matrix
    return (matrix,)


@app.cell
def _(matrix):
    matrix.value
    return


@app.cell
def _(mo, np):
    mo.hstack(
        [mo.ui.matrix(np.ones(3)), mo.ui.matrix(np.ones((1, 3)))],
        justify="start",
        gap=2,
    )
    return


if __name__ == "__main__":
    app.run()
