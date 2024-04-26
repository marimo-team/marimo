# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.4.5"
app = marimo.App(width="full")


@app.cell
def __():
    import pandas as pd
    import numpy as np
    import marimo as mo
    return mo, np, pd


@app.cell
def __(mo):
    mo.md(
        """
    This highlights some of the differences between displaying data in different libraries: polars, pandas, pyarrow, and dictionaries.

    These differences are due to how each library prints their data as CSVs.
    """
    )
    return


@app.cell
def __(np, pd):
    data = {
        "Integer": [1, 2, 3],
        "Float": [1.0, 2.5, 3.5],
        "String": ["apple", "banana", "cherry"],
        "Boolean": [True, False, True],
        "LargeInt": np.array([1e12, 2e12, 3e12], dtype=np.int64),
        "LargeFloat": np.array(
            [1.234567890123456789, 2.234567890123456789, 3.234567890123456789],
            dtype=np.float64,
        ),
        "DateTime": pd.to_datetime(["2021-01-01", "2021-06-01", "2021-09-01"]),
        "Timedelta": pd.to_timedelta(["1 days", "2 days", "3 days"]),
        "Categorical": pd.Categorical(["test", "train", "test"]),
        "NumpyArray": [
            np.array([1, 2, 3]),
            np.array([4, 5, 6]),
            np.array([7, 8, 9]),
        ],
        "Duration": pd.to_timedelta(["10:00:00", "15:30:00", "20:45:00"]),
        "Series": [
            pd.Series([1, 2, 3]),
            pd.Series([1, 2, 3]),
            pd.Series([1, 2, 3]),
        ],
        "Nested": [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}],
        "Mixed": [1, 1.1, "1"],
        "Mixed 2": [True, np.array([1, 2, 3]), pd.to_datetime("2021-01-01")],
        "Null": [None, None, None],
        "NaN": [np.nan, np.nan, np.nan],
        "Infinity": [np.inf, np.inf, np.inf],
        "Negative Infinity": [-np.inf, -np.inf, -np.inf],
        "Zero": [0, 0, 0],
        "Empty": ["", "", ""],
        "Empty List": [[], [], []],
        "Empty Dict": [{}, {}, {}],
        "Set": [set(), set(["a", "b"]), set([1, 2])],
        "Empty Tuple": [(), (), ()],
    }
    return data,


@app.cell
def __(pd):
    df_with_date_index = pd.DataFrame(
        {
            "a": [1, 2, 3],
            "b": [4, 5, 6],
            "c": [7, 8, 9],
        },
        index=pd.to_datetime(["2021-01-01", "2021-06-01", "2021-09-01"]),
    )
    return df_with_date_index,


@app.cell
def __(df_with_date_index, mo):
    mo.ui.table(df_with_date_index, label="Pandas with date index")
    return


@app.cell
def __(df_with_date_index):
    df_with_date_index
    return


@app.cell
def __(df, mo):
    mo.ui.table(df, label="Pandas")
    return


@app.cell
def __(data, pd):
    df = pd.DataFrame(data)
    df
    return df,


@app.cell
def __(df, mo):
    mo.ui.dataframe(df)
    return


@app.cell
def __(df, mo):
    mo.ui.table(df.to_dict(orient="records"), label="List of dictionaries")
    return


@app.cell
def __(data_2, mo, pd):
    # Arrow
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(pd.DataFrame(data_2))
    mo.ui.table(table, label="Pyarrow")
    return pa, pq, table


@app.cell
def __(np, pd):
    data_2 = {
        "Integer": [1, 2, 3],
        "Float": [1.0, 2.5, 3.5],
        "String": ["apple", "banana", "cherry"],
        "Boolean": [True, False, True],
        "LargeInt": np.array([1e12, 2e12, 3e12], dtype=np.int64),
        "LargeFloat": np.array(
            [1.234567890123456789, 2.234567890123456789, 3.234567890123456789],
            dtype=np.float64,
        ),
        "DateTime": pd.to_datetime(["2021-01-01", "2021-06-01", "2021-09-01"]),
        # Not support in polars
        # 'Timedelta': pd.to_timedelta(['1 days', '2 days', '3 days']),
        # 'Categorical': pd.Categorical(['test', 'train', 'test']),
        # CSV does not support nested data
        # 'NumpyArray': [np.array([1, 2, 3]), np.array([4, 5, 6]), np.array([7, 8, 9])],
        # 'Nested': [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}, {'a': 5, 'b': 6}],
        # 'Duration': pd.to_timedelta(['10:00:00', '15:30:00', '20:45:00'])
        # 'Mixed': [1, 1.1, '1'],
        # Mixed 2 is not supported in polars
        # 'Mixed 2': [True, np.array([1, 2, 3]), pd.to_datetime('2021-01-01')],
        "Null": [None, None, None],
        "NaN": [np.nan, np.nan, np.nan],
        "Infinity": [np.inf, np.inf, np.inf],
        "Negative Infinity": [-np.inf, -np.inf, -np.inf],
        "Zero": [0, 0, 0],
        "Empty": ["", "", ""],
        # More nested not supported
        # 'Empty List': [[], [], []],
        # 'Empty Dict': [{}, {}, {}],
        # 'Empty Set': [set(), set(), set()],
        # 'Empty Tuple': [(), (), ()],
    }
    return data_2,


@app.cell
def __(data_2, mo):
    # Polars
    import polars as pl

    pl_df = pl.DataFrame(data_2)
    mo.ui.table(pl_df, label="Polars")
    return pl, pl_df


@app.cell
def __(pl_df):
    pl_df
    return


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()
