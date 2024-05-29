# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.6.11"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def __(data, mo):
    options = data.list_datasets()
    dropdown = mo.ui.dropdown(options)
    dropdown
    return dropdown, options


@app.cell
def __(data, dropdown, mo):
    mo.stop(not dropdown.value)
    df = data.__call__(dropdown.value)
    return df,


@app.cell
def __(df):
    import polars as pl
    polars_df = pl.DataFrame(df)
    return pl, polars_df


@app.cell
def __(df):
    import pyarrow as pa
    pyarrow_df = pa.Table.from_pandas(df)
    return pa, pyarrow_df


if __name__ == "__main__":
    app.run()
