import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    import datetime as dt

    date_range = mo.ui.date_range(
        start=dt.date(2023, 1, 1), stop=dt.date(2023, 12, 31)
    )
    date_range
    return (date_range,)


@app.cell
def _(date_range):
    date_range.value
    return


if __name__ == "__main__":
    app.run()
