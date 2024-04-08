# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas: DataFrames: Group Timeseries by Frequency
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        You can group timestamped data into intervals of arbitrary duration using a Grouper object to specify groupby instructions.  The `freq` parameter is a string that may contain an integer followed by an [offset alias](https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases).  E.g. To see output for 2 minute long intervals:
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    df = pd.DataFrame(
        {
            "time": [
                "2022-09-01 00:00:01-07:00",
                "2022-09-01 00:00:02-07:00",
                "2022-09-01 00:01:00-07:00",
                "2022-09-01 00:02:00-07:00",
                "2022-09-01 00:03:00-07:00",
                "2022-09-01 00:04:00-07:00",
                "2022-09-01 00:05:00-07:00",
                "2022-09-01 00:07:00-07:00",
            ],
            "requests": [1, 1, 1, 1, 1, 1, 1, 1],
        }
    )
    df["time"] = pd.to_datetime(df.time)

    df.groupby(pd.Grouper(key="time", freq="2min")).sum()
    return df, pd


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
