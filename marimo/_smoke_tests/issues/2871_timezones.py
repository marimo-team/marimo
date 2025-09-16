import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    from datetime import datetime, date

    d = datetime(2010, 10, 7, 13, 15)

    # It should appear as 2010-10-07T13:15:00.000
    pl.DataFrame({"timestamp": [d], "date": [d.date()]})
    return d, date, pl


@app.cell
def _(d):
    # It should appear as 2010-10-07T13:15:00.000
    [d, d.date()]
    return


@app.cell
def _(date, pl):
    import altair as alt

    data = pl.DataFrame(
        {
            "Date": [
                date(2021, 1, 1),
                date(2021, 1, 2),
                date(2021, 1, 3),
            ],
            "Value": [23, 45, 67],
        }
    )
    alt.Chart(data).mark_line().encode(x="Date:T", y="Value:Q").interactive()
    return


if __name__ == "__main__":
    app.run()
