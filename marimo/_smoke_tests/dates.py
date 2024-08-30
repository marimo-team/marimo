# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.8.7"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    import datetime

    start_date = mo.ui.date(
        label="Start date",
        start=datetime.date(2020, 1, 1),
        stop=datetime.date(2020, 12, 31),
    )
    end_date = mo.ui.date(
        label="End date",
        start=datetime.date(2020, 1, 1),
        stop=datetime.date(2020, 12, 31),
    )
    return datetime, end_date, start_date


@app.cell
def __(end_date, mo, start_date):
    mo.hstack(
        [
            mo.hstack([start_date, "➡️", end_date]).left(),
            mo.md(f"From {start_date.value} to {end_date.value}"),
        ]
    )
    return


@app.cell
def __(datetime, mo):
    start_datetime = mo.ui.datetime(
        label="Start datetime",
        start=datetime.datetime(2021, 1, 1),
        stop=datetime.datetime(2021, 12, 31),
    )
    end_datetime = mo.ui.datetime(
        label="End datetime",
        start=datetime.datetime(2021, 1, 1),
        stop=datetime.datetime(2021, 12, 31),
    )
    return end_datetime, start_datetime


@app.cell
def __(end_datetime, mo, start_datetime):
    mo.hstack(
        [
            mo.hstack([start_datetime, "➡️", end_datetime]).left(),
            mo.md(f"From {start_datetime.value} to {end_datetime.value}"),
        ]
    )
    return


@app.cell
def __(datetime, mo):
    date_range_input = mo.ui.date_range(
        label="Date_range",
        start=datetime.date(2021, 1, 1),
        stop=datetime.date(2021, 12, 31),
    )
    return date_range_input,


@app.cell
def __(date_range_input, mo):
    mo.hstack([date_range_input, date_range_input.value])
    return


@app.cell
def __(mo):
    _date = mo.ui.date(label="Input")
    _datetime = mo.ui.datetime(label="Input")
    _date_range = mo.ui.date_range(label="Input")
    return


if __name__ == "__main__":
    app.run()
