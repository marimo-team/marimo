# /// script
# requires-python = "<=3.13"
# dependencies = [
#     "altair==5.5.0",
#     "dask==2025.9.1",
#     "duckdb==1.2.2",
#     "ibis-framework[duckdb]==10.8.0",
#     "marimo",
#     "pandas==2.3.3",
#     "polars",
# ]
# ///

import marimo

__generated_with = "0.16.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import sys
    import polars as pl
    import ibis
    import pandas as pd
    import narwhals as nw

    ibis.options.interactive = True
    return mo, nw, pl


@app.cell
def _(pl):
    df_base = pl.read_csv(
        "https://github.com/uwdata/mosaic/raw/main/data/athletes.csv"
    )
    return (df_base,)


@app.cell(hide_code=True)
def _(mo):
    backend = mo.ui.dropdown(
        [
            "pandas",
            "polars",
            ["pyarrow", "ibis"],
            "pyarrow",
            ["pyarrow", "dask"],
            ["pyarrow", "duckdb"],
        ],
        value="pandas",
        label="Backend",
    )
    backend
    return (backend,)


@app.cell
def _(backend, df_base, nw):
    _v = backend.value
    if isinstance(_v, list):
        df = nw.from_arrow(df_base, backend=_v[0]).lazy(_v[1]).to_native()
    else:
        df = nw.from_arrow(df_base, backend=_v).to_native()
    return (df,)


@app.cell
def _(backend, mo):
    mo.md("##" + str(backend.value))
    return


@app.cell
def _(df):
    df
    return


@app.cell
def _(df, mo):
    mo.ui.dataframe(df)
    return


if __name__ == "__main__":
    app.run()
