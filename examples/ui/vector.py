import marimo

__generated_with = "0.19.11"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import numpy as np

    return mo, np


@app.cell
def _(mo):
    hstack = lambda x: mo.hstack(x, justify="start")
    return (hstack,)


@app.cell
def _(mo):
    v1 = mo.ui.vector([1, 1, 1])
    v2 = mo.ui.vector([1, 1, 1], transpose=True)
    return v1, v2


@app.cell
def _(mo, np, v1, v2):
    v3 = mo.ui.matrix(np.outer(v1.value, v2.value))
    return (v3,)


@app.cell
def _(hstack, v1, v2, v3):
    hstack([v1, v2, "=", v3])
    return


if __name__ == "__main__":
    app.run()
