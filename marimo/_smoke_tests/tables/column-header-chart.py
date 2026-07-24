# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "numpy",
#     "pandas",
#     "polars",
#     "requests",
# ]
# ///

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import pandas as pd
    import polars as pl

    return mo, np, pd, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Column header charts

    Visual smoke tests for table column-summary charts. Charts only render when
    the table has at least 11 rows (`DEFAULT_SUMMARY_CHARTS_MINIMUM_ROWS`).

    Related: [#7046](https://github.com/marimo-team/marimo/issues/7046),
    [#10303](https://github.com/marimo-team/marimo/issues/10303).

    **Check the browser console** on the null/NaN sections — there should be no
    Vega `Infinite extent` or `Dropping ... aggregate max` warnings.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Happy path — enums / categoricals
    """)
    return


@app.cell
def _(pl):
    # Enums and categorical data types
    bears_enum = pl.Enum(["Polar", "Panda", "Brown"])

    enums_cats = pl.DataFrame(
        {
            "bears": ["Polar", "Panda", "Brown", "Brown", "Polar"] * 30,
            "bears_cat": ["Polar", "Panda", "Brown", "Brown", "Polar"] * 30,
        },
        schema={
            "bears": bears_enum,
            "bears_cat": pl.Categorical,
        },
    )
    enums_cats
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## All-null / all-NaN numeric — #10303

    Expect a thin orange null bar only (no empty histogram strip). No Vega
    console warnings.
    """)
    return


@app.cell
def _(mo, np, pd):
    all_nan_df = pd.DataFrame(
        {
            "id": list(range(12)),
            "all_nan": [np.nan] * 12,
            "all_none": [None] * 12,
        }
    )
    mo.ui.table(all_nan_df)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Mixed columns with all-NaN — #10303 repro

    Column `b` is all-NaN; `c` is half null / half constant. Toggle `N` below
    the chart threshold (charts off when `2N < 11`).
    """)
    return


@app.cell
def _(mo):
    n = mo.ui.slider(1, 20, value=6, label="N (rows = 2N)")
    n
    return (n,)


@app.cell
def _(mo, n, np, pd):
    N = n.value
    issue_df = pd.DataFrame(
        {
            "a": list("xy") * N,
            "b": [np.nan, np.nan] * N,
            "c": ([1, None] * N),
        }
    )
    mo.vstack(
        [
            mo.md(
                f"`{len(issue_df)}` rows — charts enabled: **{len(issue_df) >= 11}**"
            ),
            mo.ui.table(issue_df),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Temporal all-null

    All-null date/datetime columns. Charts should not spam the console; nulls
    may render as a single bar (temporal path differs from numeric).
    """)
    return


@app.cell
def _(mo, pl):
    temporal_null_df = pl.DataFrame(
        {
            "id": list(range(12)),
            "all_null_date": [None] * 12,
            "all_null_datetime": [None] * 12,
        },
        schema={
            "id": pl.Int64,
            "all_null_date": pl.Date,
            "all_null_datetime": pl.Datetime,
        },
    )
    mo.ui.table(temporal_null_df)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Mixed nulls + values (numeric)

    Null bar + histogram `hconcat`. Should look normal; no console warnings.
    """)
    return


@app.cell
def _(mo, np, pd):
    mixed_df = pd.DataFrame(
        {
            "mostly_valid": [1, 2, 3, 4, 5, 6, None, 8, 9, 10, 11, 12],
            "half_null": [1, None, 2, None, 3, None, 4, None, 5, None, 6, None],
            "single_value_plus_nulls": [7.0] * 6 + [np.nan] * 6,
        }
    )
    mo.ui.table(mixed_df)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Below chart threshold (< 11 rows)

    Stats only — no charts. Should not print a Python `RuntimeWarning`
    (`Mean of empty slice`) for all-NaN columns (#7046).
    """)
    return


@app.cell
def _(np, pd):
    small_nan_df = pd.DataFrame(
        {"a": [1, 2, 3], "b": [np.nan, np.nan, np.nan]}
    )
    small_nan_df
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Polars all-null numeric

    Same all-null case via Polars (backend null-count path).
    """)
    return


@app.cell
def _(mo, pl):
    polars_all_null = pl.DataFrame(
        {
            "id": list(range(12)),
            "all_null_float": [None] * 12,
            "all_null_int": [None] * 12,
        },
        schema={
            "id": pl.Int64,
            "all_null_float": pl.Float64,
            "all_null_int": pl.Int64,
        },
    )
    mo.ui.table(polars_all_null)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Remote / larger tables

    Sanity-check charts still work on real-ish data.
    """)
    return


@app.cell
def _(pl):
    pokemon_url = "https://gist.githubusercontent.com/armgilles/194bcff35001e7eb53a2a8b441e8b2c6/raw/92200bc0a673d5ce2110aaad4544ed6c4010f687/pokemon.csv"
    pl.read_csv(pokemon_url)
    return


@app.cell
def _(pl):
    import io
    import zipfile

    import requests

    train_parquet_link = "https://www.kaggle.com/api/v1/datasets/download/shahmirvarqha/train-stations-amsterdam"

    response = requests.get(train_parquet_link)
    zip_data = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_data) as z:
        parquet_file_name = [f for f in z.namelist() if f.endswith(".parquet")][
            0
        ]
        with z.open(parquet_file_name) as parquet_file:
            trains_df = pl.read_parquet(parquet_file)

    trains_df[:20000]
    return


if __name__ == "__main__":
    app.run()
