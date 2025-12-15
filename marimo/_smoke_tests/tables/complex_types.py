import marimo

__generated_with = "0.18.3"
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
            "lists_with_enum": pl.Series(
                "lists_with_enum",
                [["A", "B"], ["A", "B"], ["A", "B"]],
                dtype=pl.List(pl.Enum(categories=["A", "B"])),
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

    # df = pl.concat([df]*10, rechunk=True).with_row_count(name="idx")

    mo.ui.table(df)
    return df, mo, pl


@app.cell
def _(df):
    pandas = df.to_pandas()
    pandas
    return


@app.cell(hide_code=True)
def _(mo, pd, pl):
    complex = [1 + 2j, 2 + 3j]

    additional_types_pd = pd.DataFrame(
        {
            "complex": complex,
            "bigint": [2**64, 2**127],
            "list_big_ints": [[1253397962952480469], [1253397962952480469]],
            "large_floats": [[125339796295248046.9], [-12533979629524804.69]],
        }
    )
    additional_types_pl = pl.DataFrame(
        {
            "complex": complex,
            "bigint": [2**64, -(2**65)],
            "list_big_ints": [[1253397962952480469], [1253397962952480469]],
            "large_floats": [[125339796295248046.9], [-12533979629524804.69]],
        }
    )
    mo.vstack([mo.md("#### BigInts"), additional_types_pd, additional_types_pl])
    return


@app.cell(hide_code=True)
def _(mo, pd):
    from decimal import Decimal

    _data = {
        "decimals": [
            Decimal("23.546"),
            Decimal("12.431"),
            Decimal("-12.3232"),
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-0"),
            Decimal("-Infinity"),
        ]
    }

    mo.vstack(
        [
            mo.md("#### Decimals"),
            mo.hstack(
                [
                    mo.plain(pd.DataFrame(_data)),
                    pd.DataFrame(_data),
                ],
                justify="start",
            ),
        ]
    )
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


@app.cell(hide_code=True)
def _(mo, pd, pl):
    import uuid

    uuid_data = {
        "id": [
            uuid.UUID("00000000-0000-0000-0000-000000000000"),
            uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
            uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
        ],
        "name": ["test1", "test2", "test3"],
    }

    uuid_df = pd.DataFrame(uuid_data)
    uuid_polars = pl.DataFrame(uuid_data)

    mo.vstack([mo.md("#### UUIDs"), mo.plain(uuid_df), uuid_df, uuid_polars])
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


@app.cell
def _(df, mo):
    subset = df.drop(["nested_lists", "list_with_structs", "nested_arrays"])
    mo.ui.data_editor(subset)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Stress testing

    We can use a large dataset to stress test our rendering, charting. Notebook credit to Vincent: [WoW Dataset](https://github.com/koaning/wow-avatar-datasets)

    ~36 million rows, 7 columns
    """)
    return


@app.cell
def _():
    # wow_data = pl.scan_parquet(
    #     "https://github.com/koaning/wow-avatar-datasets/raw/refs/heads/main/wow-full.parquet"
    # )
    # wow_data
    # wow_data.collect()
    return


if __name__ == "__main__":
    app.run()
