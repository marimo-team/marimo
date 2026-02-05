# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "vega-datasets",
#     "marimo",
#     "polars",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    from vega_datasets import data
    import polars as pl
    return data, mo, pl


@app.cell
def _(data, pl):
    df = pl.from_pandas(data.cars())
    df
    return (df,)


@app.cell
def _(df, mo):
    mo.ui.table(df)
    return


@app.cell
def _(df, mo):
    mo.plain(df)
    return


@app.cell
def _(df, mo):
    mo.hstack(["hstack", mo.vstack(["vstack", df])])
    return


@app.cell
def _(df, mo):
    mo.hstack(["hstack", mo.vstack(["vstack", mo.plain(df)])])
    return


if __name__ == "__main__":
    app.run()
