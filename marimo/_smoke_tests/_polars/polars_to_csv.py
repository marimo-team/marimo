# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars>=2.0.0",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
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
            "date": [
                datetime.date(2021, 1, 1),
                datetime.date(2021, 1, 2),
                datetime.date(2021, 1, 3),
            ],
            "struct": [
                {"a": 1, "b": 2},
                {"a": 3, "b": 4},
                {"a": 5, "b": 6},
            ],
            "list": [[1, 2], [3, 4], [5, 6]],
            "array": [[1, 2, 3], [4], []],
            "nulls": [None, "data", None],
            "map_strings": pl.Series(
                [{"greeting": "こんにちは", "quoted": 'a, "value"'}, {}, None],
                dtype=pl.Map(pl.String, pl.String),
            ),
            "map_int_keys": pl.Series(
                [{1: [1, 2], 2: None}, {}, None],
                dtype=pl.Map(pl.Int64, pl.List(pl.Int64)),
            ),
            "categorical": pl.Series(["cat", "dog", "mouse"]).cast(
                pl.Categorical
            ),
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
    return complex_data, mo


@app.cell
def _(complex_data, mo):
    mo.plain(complex_data)
    return


@app.cell
def _(complex_data):
    complex_data
    return


@app.cell
def _(complex_data, mo):
    _maps = complex_data.select("int", "map_strings", "map_int_keys")
    mo.vstack(
        [
            mo.md(
                "## Map downloads\nDownload CSV or TSV from each table to compare eager and lazy exports."
            ),
            mo.ui.tabs(
                {
                    "Eager": mo.ui.table(_maps),
                    "Lazy": mo.ui.table(_maps.lazy()),
                }
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
