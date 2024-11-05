import marimo

__generated_with = "0.9.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import polars as pl
    from datetime import datetime, date, time
    import marimo as mo

    df = pl.DataFrame(
        {
            "price": [40, 50],
            "datetime": [datetime(2020, 1, 1), datetime(2020, 1, 2)],
        }
    )
    df
    return date, datetime, df, mo, pl, time


@app.cell
def __(df, pl):
    df.with_columns(pl.col("datetime").dt.replace_time_zone("Asia/Kathmandu"))
    return


@app.cell
def __(date, pl):
    df2 = pl.DataFrame(
        {
            "price": [40, 50],
            "date": [date(2020, 1, 1), date(2020, 1, 2)],
        }
    )
    df2
    return (df2,)


@app.cell
def __(pl, time):
    df3 = pl.DataFrame(
        {
            "price": [40, 50],
            "time": [time(1, 30), time(2, 30)],
        }
    )
    df3
    return (df3,)


if __name__ == "__main__":
    app.run()
