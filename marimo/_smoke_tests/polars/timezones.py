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
            "tz_america": [
                datetime(
                    2010, 10, 7, 5, 15, tzinfo=pytz.timezone("America/New_York")
                )
            ],
            "no_tz": [datetime(2010, 10, 7, 5, 15)],
        }
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
