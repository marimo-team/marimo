# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.23"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import pandas as pd

    data = {"col3": range(3), "col1": [0, 1, 2], "col2": [6, 5, 4]}

    df = pd.DataFrame(data)
    df_with_index = pd.DataFrame(data, index=[0, 1, 2])
    df_with_named_index = pd.DataFrame(data)
    df_with_named_index.index.names = ["idx"]
    return data, df, df_with_index, df_with_named_index, mo, pd


@app.cell
def __(pd):
    _data = pd.DataFrame(
        {
            "Animal": ["Falcon", "Falcon", "Parrot", "Parrot"],
            "Max Speed": [380.0, 370.0, 24.0, 26.0],
        }
    )
    agg_df = _data.groupby(["Animal"]).mean()
    return agg_df,


@app.cell
def __(df, df_with_index, df_with_named_index):
    [
        df.index,
        df_with_index.index,
        df_with_named_index.index,
    ]
    return


@app.cell
def __(agg_df, mo):
    mo.ui.table(agg_df)
    return


@app.cell
def __(df, mo):
    mo.ui.table(df)
    return


@app.cell
def __(df_with_index, mo):
    mo.ui.table(df_with_index)
    return


@app.cell
def __(df_with_named_index, mo):
    mo.ui.table(df_with_named_index)
    return


if __name__ == "__main__":
    app.run()
