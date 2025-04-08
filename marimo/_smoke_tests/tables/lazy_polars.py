

import marimo

__generated_with = "0.12.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    return mo, pl


@app.cell
def _(pl):
    # ~1-2 seconds
    df = pl.scan_parquet(
        "hf://datasets/google-research-datasets/go_emotions/raw/train-00000-of-00001.parquet"
    )
    return (df,)


@app.cell
def _(df, mo):
    # ~100-300ms
    mo.plain(df)
    return


@app.cell
def _(df):
    # ~2-5 seconds
    # TODO: Fix this
    df
    return


@app.cell
def _(df, mo):
    # ~2-5 seconds
    # TODO: Fix this
    mo.ui.table.lazy(df)
    return


@app.cell
def _(df):
    df.collect_schema()
    return


if __name__ == "__main__":
    app.run()
