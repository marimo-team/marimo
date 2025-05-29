import marimo

__generated_with = "0.13.14"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import polars as pl
    import numpy as np
    from datetime import datetime, date, time
    import marimo as mo

    df = pl.DataFrame(
        {
            # Numeric
            "integers": pl.Series("integers", [1, 2, 3], dtype=pl.Int32),
            "floats": pl.Series("floats", [1.0, 2.0, 3.0], dtype=pl.Float64),
            # String
            "strings": pl.Series("strings", ["a", "b", "c"], dtype=pl.Utf8),
            "categories": pl.Series(
                "categories", ["a", "b", "c"], dtype=pl.Categorical
            ),
            # Boolean
            "bools": pl.Series("bools", [True, False, True], dtype=pl.Boolean),
            # Temporal
            "dates": pl.Series(
                "dates",
                [date(2021, 1, 1), date(2021, 2, 2), date(2021, 3, 3)],
                dtype=pl.Date,
            ),
            "times": pl.Series("times", [time(12, 0, 0)] * 3, dtype=pl.Time),
            "datetimes": pl.Series(
                "datetimes", [datetime.now()] * 3, dtype=pl.Datetime
            ),
            "durations": pl.Series(
                "durations", ["1d", "2d", "3d"], dtype=pl.Duration
            ),
            # Lists
            "lists": pl.Series(
                "lists", [[1, 2], [3, 4], [5, 6]], dtype=pl.List(pl.Int64)
            ),
            "nested_lists": pl.Series(
                "nested_lists",
                [[[1, 2]], [[3, 4]], [[5, 6]]],
                dtype=pl.List(pl.List(pl.Int64)),
            ),
            "arrays": pl.Series(
                "arrays",
                [[1, 2], [3, 4], [5, 6]],
                dtype=pl.Array(pl.Int64, shape=(2,)),
            ),
            "nested_arrays": pl.Series(
                "nested_arrays",
                [[[1, 2]], [[3, 4]], [[5, 6]]],
                dtype=pl.Array(pl.Array(pl.Int64, shape=(2,)), shape=(1,)),
            ),
            # Objects
            "sets": pl.Series(
                "sets", [set([1, 2]), set([3, 4]), set([5, 6])], dtype=pl.Object
            ),
            "dicts": pl.Series(
                "dicts",
                [{"a": 1, "b": 2}, {"c": 3, "d": 4}, {"e": 5, "f": 6}],
                dtype=pl.Object,
            ),
            # Structs
            "structs": pl.Series(
                [{"a": 1, "b": 2}, {"c": 3, "d": 4}, {"e": 5, "f": 6}],
                dtype=pl.Struct,
            ),
            # Mixed
            "structs_with_list": pl.Series(
                "mixed",
                [{"a": [1, 2], "b": 2}, {"a": [3, 4], "b": 4}, [5, 6]],
            ),
            "list_with_structs": pl.Series(
                "list_with_structs",
                [
                    [{"a": 1}, {"c": 3}],
                    [{"e": 5}],
                    [],
                ],
            ),
            # Nulls
            "nulls": pl.Series("nulls", [None, None, None], dtype=pl.Utf8),
            # Complex
            "complex": pl.Series(
                "complex",
                [1 + 2j, 3 + 4j, 5 + 6j],
                dtype=pl.Object,
            ),
        }
    )
    mo.ui.table(df)
    return df, mo, pl


@app.cell
def _(df):
    pandas = df.to_pandas()
    pandas
    return


@app.cell
def _(mo, pd, pl):
    additional_types_pd = pd.DataFrame(
        {"complex": [1 + 2j, 2 + 3j], "bigint": [2**64, 2**127]}
    )
    additional_types_pl = pl.DataFrame(
        {"complex": [1 + 2j, 2 + 3j], "bigint": [2**64, 2**65]}
    )
    mo.vstack([additional_types_pd, additional_types_pl])
    return


@app.cell
def _():
    # arrow = df.to_arrow()
    # arrow
    return


@app.cell
def _(df, mo):
    mo.ui.dataframe(df)
    return


@app.cell
def _(mo):
    import pandas as pd

    pandas_with_timestamp = pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2021-01-01"),
                pd.Timestamp("2021-01-02"),
                pd.Timestamp("2021-01-03"),
            ]
        }
    )
    mo.ui.dataframe(pandas_with_timestamp)
    return (pd,)


if __name__ == "__main__":
    app.run()
