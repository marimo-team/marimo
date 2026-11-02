# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas",
#     "polars",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import polars as pl

    return mo, pd, pl


@app.cell
def _(pd):
    data = {
        "A": [True, True, True],
        "B": [False, False, False],
        "C": [True, True, False],
    }

    pd.DataFrame(data)
    return (data,)


@app.cell
def _(data: dict, pl):
    pl.DataFrame(data)


@app.cell
def _(data: dict, mo):
    t = mo.ui.table(data)
    t
    return (t,)


@app.cell
def _(t):
    t.value


if __name__ == "__main__":
    app.run()
