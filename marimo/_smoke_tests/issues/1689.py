# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    data = {"col3": range(3), "col1": [0, 1, 2], "col2": [6, 5, 4]}

    df = pd.DataFrame(data)
    df_with_index = pd.DataFrame(data, index=[0, 1, 2])
    df_with_named_index = pd.DataFrame(data)
    df_with_named_index.index.names = ["idx"]
    return df, df_with_index, df_with_named_index, mo, pd


@app.cell
def _(pd):
    _data = pd.DataFrame(
        {
            "Animal": ["Falcon", "Falcon", "Parrot", "Parrot"],
            "Max Speed": [380.0, 370.0, 24.0, 26.0],
        }
    )
    agg_df = _data.groupby(["Animal"]).mean()
    return (agg_df,)


@app.cell
def _(df, df_with_index, df_with_named_index):
    [
        df.index,
        df_with_index.index,
        df_with_named_index.index,
    ]
    return


@app.cell
def _(agg_df, mo):
    mo.ui.table(agg_df)
    return


@app.cell
def _(df, mo):
    mo.ui.table(df)
    return


@app.cell
def _(df_with_index, mo):
    mo.ui.table(df_with_index)
    return


@app.cell
def _(df_with_named_index, mo):
    mo.ui.table(df_with_named_index)
    return


if __name__ == "__main__":
    app.run()
