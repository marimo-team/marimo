import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl_lib
    import pandas as pd_lib
    from datetime import datetime, date, time
    import sys

    sys.tracebacklimit = 1
    return date, datetime, pd_lib, pl_lib, time


@app.cell(hide_code=True)
def _(mo, pd_lib, pl_lib):
    df_library = mo.ui.dropdown(
        {
            "Polars": pl_lib,
            "Pandas": pd_lib,
        },
        label="Dataframe library",
        value="Polars",
    )
    df_library
    return (df_library,)


@app.cell
def _(df_library):
    pl = df_library.value
    return (pl,)


@app.cell(hide_code=True)
def _():
    import marimo as mo


    def print_df(df):
        return mo.hstack([df, mo.plain(df)])
    return mo, print_df


@app.cell
def _(datetime, pl, print_df):
    df = pl.DataFrame(
        {
            "price": [40, 50],
            "datetime": [datetime(2020, 1, 1), datetime(2020, 1, 2)],
        }
    )

    print_df(df)
    return (df,)


@app.cell
def _(df, print_df):
    import narwhals as nw

    _df = (
        nw.from_native(df)
        .with_columns(nw.col("datetime").dt.replace_time_zone("Asia/Kathmandu"))
        .to_native()
    )

    print_df(_df)
    return


@app.cell
def _(date, pl, print_df):
    _df = pl.DataFrame(
        {"price": [40, 50], "date": [date(2020, 1, 1), date(2020, 1, 2)]}
    )
    print_df(_df)
    return


@app.cell
def _(pl, print_df, time):
    _df = pl.DataFrame(
        {
            "price": [40, 50],
            "time": [time(1, 30), time(2, 30)],
        }
    )
    print_df(_df)
    return


if __name__ == "__main__":
    app.run()
