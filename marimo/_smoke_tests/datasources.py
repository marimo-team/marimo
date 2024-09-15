# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "vega-datasets",
#     "marimo",
#     "polars",
#     "pyarrow",
# ]
# ///

import marimo

__generated_with = "0.8.13"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    from vega_datasets import data
    import pandas as pd
    return data, mo, pd


@app.cell
def __(pd):
    editable_table = pd.DataFrame({"a": [2, 2, 12], "b": [2, 5, 6]})
    return editable_table,


@app.cell
def __(pd):
    df_with_list = pd.DataFrame([{"a": [1, 2, 3]}])
    return df_with_list,


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


@app.cell
def __(mo, polars_df):
    mo.ui.table(polars_df)
    return


@app.cell
def __(mo, pyarrow_df):
    mo.ui.table(pyarrow_df)
    return


@app.cell
def __(df, mo):
    mo.ui.table(df)
    return


@app.cell
def __(mo, polars_df):
    _df = mo.sql(
        f"""
        SELECT * FROM polars_df
        """
    )
    return


@app.cell
def __(mo):
    mo.ui.table({"a": [2, 2, 12], "b": [2, 5, 6]})
    return


@app.cell
def __(mo, polars_df):
    mo.plain(polars_df)
    return


@app.cell
def __(pd):
    date_range = pd.date_range(start="2023-01-01", periods=10, freq="D")
    date_indexed_df = pd.DataFrame({"Data": range(10)}, index=date_range)
    date_indexed_df
    return date_indexed_df, date_range


if __name__ == "__main__":
    app.run()
