import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
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
    return alt, df, mo


@app.cell
def _(alt, df):
    alt.data_transformers.enable("marimo_csv")
    df.plot.line(x="date", y="price", color="stock")
    return


@app.cell
def _(alt, df):
    alt.data_transformers.enable("marimo_json")
    df.plot.line(x="date", y="price", color="stock")
    return


@app.cell
def _(alt, df):
    alt.data_transformers.enable("default")
    df.plot.line(x="date", y="price", color="stock")
    return


@app.cell
def _(df, mo):
    mo.ui.altair_chart(df.plot.line(x="date", y="price", color="stock"))
    return


if __name__ == "__main__":
    app.run()
