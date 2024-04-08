# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Reshape to have 1 row per value in a list column
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        Creates a new DataFrame that is a transformed version of the input. E.g.
        *   Input: df with a column named `msg_ids` that is a list of values (i.e. many per row, at least in some rows).
        *   Output: new_df which has 1 row per unique value found in any of the original `msg_ids` lists, with that value in a new column named `msg_id`.

        """
    )
    return


@app.cell
def __():
    import pandas as pd

    df = pd.DataFrame(
        {
            "date": ["9/1/22", "9/2/22", "9/3/22"],
            "action": ["Add", "Update", "Delete"],
            "msg_ids": [[1, 2, 3], [], [2, 3]],
        }
    )
    df.set_index("date", inplace=True)

    temp_series = df["msg_ids"].apply(pd.Series, 1).stack()
    temp_series.index = temp_series.index.droplevel(-1)
    temp_series.name = "msg_id"
    new_df = temp_series.to_frame()
    new_df.set_index("msg_id", inplace=True)
    new_df.loc[~new_df.index.duplicated(), :]  # Drop duplicates.
    return df, new_df, pd, temp_series


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
