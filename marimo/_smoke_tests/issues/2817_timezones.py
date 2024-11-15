import marimo

__generated_with = "0.9.19"
app = marimo.App(width="medium")


@app.cell
def __():
    import polars as pl
    from datetime import datetime, date

    d = datetime(2010, 10, 7, 13, 15)

    pl.DataFrame({"timestamp": [d], "date": [d.date()]})
    return d, date, datetime, pl


@app.cell
def __(d):
    [d, d.date()]
    return


@app.cell
def __(date, pl):
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
    return alt, data


if __name__ == "__main__":
    app.run()
