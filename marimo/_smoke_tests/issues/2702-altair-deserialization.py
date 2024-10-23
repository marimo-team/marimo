import marimo

__generated_with = "0.9.12"
app = marimo.App(width="medium")


@app.cell
def __():
    from datetime import date
    import marimo as mo
    import polars as pl
    import altair as alt

    df = pl.DataFrame(
        {
            "date": [date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 4)] * 2,
            "price": [1, 4, 6, 1, 5, 2],
            "stock": ["a", "a", "a", "b", "b", "b"],
        }
    )
    return alt, date, df, mo, pl


@app.cell
def __(alt, df):
    alt.data_transformers.enable("marimo_csv")
    df.plot.line(x="date", y="price", color="stock")
    return


@app.cell
def __(alt, df):
    alt.data_transformers.enable("marimo_json")
    df.plot.line(x="date", y="price", color="stock")
    return


@app.cell
def __(alt, df):
    alt.data_transformers.enable("default")
    df.plot.line(x="date", y="price", color="stock")
    return


@app.cell
def __(df, mo):
    mo.ui.altair_chart(df.plot.line(x="date", y="price", color="stock"))
    return


if __name__ == "__main__":
    app.run()
