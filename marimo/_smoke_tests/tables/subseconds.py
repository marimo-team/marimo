import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import datetime

    import marimo as mo
    import pandas as pd

    return datetime, mo, pd


@app.cell
def _(mo):
    mo.md(r"""
    ## Datetime
    """)


@app.cell
def _(datetime, pd):
    _start = datetime.datetime(2024, 11, 27, 16)
    _slice = datetime.timedelta(days=1)
    pd.DataFrame(
        data={
            "timestamp": [_start + n * _slice for n in range(5)],
        }
    )


@app.cell
def _(mo):
    mo.md(r"""
    ## Seconds
    """)


@app.cell
def _(datetime, pd):
    _start = datetime.datetime(2024, 11, 27, 16, 17, 7)
    _slice = datetime.timedelta(seconds=1)
    pd.DataFrame(
        data={
            "timestamp": [_start + n * _slice for n in range(5)],
        }
    )


@app.cell
def _(mo):
    mo.md(r"""
    ## Milliseconds
    """)


@app.cell
def _(datetime, pd):
    _start = datetime.datetime(2024, 11, 27, 16, 17, 7, 742951)
    _slice = datetime.timedelta(microseconds=123456)
    test_df = pd.DataFrame(
        data={
            "timestamp": [_start + n * _slice for n in range(5)],
        }
    )
    return (test_df,)


@app.cell
def _(mo, test_df):
    # Nanoseconds are still missing, because JavaScript (browsers) don't support nanoseconds.
    mo.hstack([mo.plain(test_df), test_df])


@app.cell
def _(mo):
    mo.md(r"""
    ## Nanoseconds
    """)


@app.cell
def _(test_df):
    nano_df = test_df.copy()
    nano_df["timestamp"] = nano_df["timestamp"].astype(str)
    nano_df


if __name__ == "__main__":
    app.run()
