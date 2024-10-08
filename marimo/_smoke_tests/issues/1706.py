# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.25"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import polars as pl
    import numpy as np

    df = pl.DataFrame(
        {"a": [np.zeros(5) for i in range(5)]}, schema={"a": pl.Array(pl.Float64, 5)}
    )
    df
    return df, mo, np, pl


@app.cell
def __(df, mo):
    mo.plain(df)
    return


@app.cell
def __(df):
    df.get_columns()[0].dtype
    return


if __name__ == "__main__":
    app.run()
