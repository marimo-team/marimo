# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas==2.2.3",
#     "polars==1.17.1",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import polars as pl
    return mo, pd, pl


@app.cell
def _(mo):
    num_range = mo.ui.slider(start=10, step=1, stop=100)
    num_range
    return (num_range,)


@app.cell
def _(num_range, pd):
    # Pandas Series with name
    pd_named = pd.Series(list(range(num_range.value)), name="numbers")
    pd_named
    return


@app.cell
def _(num_range, pd):
    # Pandas Series without name
    pd_unnamed = pd.Series(list(range(num_range.value)))
    pd_unnamed
    return


@app.cell
def _(num_range, pl):
    # Polars Series with name
    pl_named = pl.Series("numbers", list(range(num_range.value)))
    pl_named
    return


@app.cell
def _(num_range, pl):
    # Polars Series without name
    pl_unnamed = pl.Series(list(range(num_range.value)))
    pl_unnamed
    return


@app.cell
def _(num_range, pl):
    # Polars Series with empty string name
    pl_empty_name = pl.Series("", list(range(num_range.value)))
    pl_empty_name
    return


if __name__ == "__main__":
    app.run()
