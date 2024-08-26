# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.8"
app = marimo.App(width="medium")


@app.cell
def __():
    import datetime
    import marimo as mo
    import polars as pl

    complex_data = pl.DataFrame(
        {
            "strings": ["a", "b", "c"],
            "bool": [True, False, True],
            "int": [1, 2, 3],
            "float": [1.0, 2.0, 3.0],
            "datetime": [
                datetime.datetime(2021, 1, 1),
                datetime.datetime(2021, 1, 2),
                datetime.datetime(2021, 1, 3),
            ],
            "struct": [
                {"a": 1, "b": 2},
                {"a": 3, "b": 4},
                {"a": 5, "b": 6},
            ],
            "list": [[1, 2], [3, 4], [5, 6]],
            "array": [[1, 2, 3], [4], []],
            "nulls": [None, "data", None],
            "categorical": pl.Series(["cat", "dog", "mouse"]).cast(pl.Categorical),
            "time": [
                datetime.time(12, 30),
                datetime.time(13, 45),
                datetime.time(14, 15),
            ],
            "duration": [
                datetime.timedelta(days=1),
                datetime.timedelta(days=2),
                datetime.timedelta(days=3),
            ],
            "mixed_list": [
                [1, "two"],
                [3.0, False],
                [None, datetime.datetime(2021, 1, 1)],
            ],
        },
        strict=False,
    )
    return complex_data, datetime, mo, pl


@app.cell
def __(complex_data, mo):
    mo.plain(complex_data)
    return


@app.cell
def __(complex_data):
    complex_data
    return


if __name__ == "__main__":
    app.run()
