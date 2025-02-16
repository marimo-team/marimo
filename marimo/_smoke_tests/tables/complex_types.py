import marimo

__generated_with = "0.11.5"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import polars as pl
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
            "dates": pl.Series("dates", [date(2021, 1, 1)] * 3, dtype=pl.Date),
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
            "arrays": pl.Series(
                "arrays",
                [[1, 2], [3, 4], [5, 6]],
                dtype=pl.Array(pl.Int64, shape=(2,)),
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
    return date, datetime, df, mo, pl, time


@app.cell
def _(df):
    pandas = df.to_pandas()
    pandas
    return (pandas,)


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
    return pandas_with_timestamp, pd


if __name__ == "__main__":
    app.run()
