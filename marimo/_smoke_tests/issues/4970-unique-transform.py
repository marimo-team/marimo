import marimo

__generated_with = "0.13.10"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import polars as pl
    import ibis as ib
    from vega_datasets import data
    return data, ib, mo, pd, pl


@app.cell
def _(data, ib, pd, pl):
    iris_dataset = data.iris()
    df_pandas = pd.DataFrame(iris_dataset)
    df_polars = pl.DataFrame(iris_dataset)
    df_ibis = ib.memtable(iris_dataset)
    return df_ibis, df_pandas, df_polars


@app.cell
def _(df_pandas, mo):
    mo.ui.dataframe(df_pandas)
    return


@app.cell
def _(df_polars, mo):
    mo.ui.dataframe(df_polars)
    return


@app.cell
def _(df_ibis, mo):
    mo.ui.dataframe(df_ibis)
    return


if __name__ == "__main__":
    app.run()
