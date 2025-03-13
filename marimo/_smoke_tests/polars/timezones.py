import marimo

__generated_with = "0.11.18"
app = marimo.App(width="medium")


@app.cell
def _():
    from datetime import datetime
    import pytz
    import polars as pl

    df = pl.DataFrame(
        {
            "tz_utc": [datetime(2010, 10, 7, 5, 15, tzinfo=pytz.UTC)],
            "no_tz": [datetime(2010, 10, 8, 5, 15)],
        }
    ).with_columns(
        tz_america=pl.col("no_tz").dt.replace_time_zone("America/New_York"),
        tz_asia=pl.col("no_tz").dt.replace_time_zone("Asia/Tokyo"),
    )
    return datetime, df, pl, pytz


@app.cell
def _(df):
    df
    return


@app.cell
def _(df, mo):
    mo.plain(df)
    return


@app.cell
def _(df):
    df.to_dicts()
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
