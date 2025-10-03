import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import pandas as pd
    import polars as pl

    import marimo as mo
    return alt, mo, pd, pl


@app.cell
def _(mo, pd, pl):
    url = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"

    df_selection = mo.ui.dropdown(
        {"pandas": pd.read_csv(url), "polars": pl.read_csv(url), "url": url},
        value="polars",
    )
    df_selection
    return (df_selection,)


@app.cell
def _(alt, df_selection, mo):
    df = df_selection.value
    chart = mo.ui.altair_chart(
        alt.Chart(df)
        .mark_point()
        .encode(x="sepal_length:Q", y="sepal_width:Q")
    )
    chart
    return chart, df


@app.cell
def _(chart):
    chart.data
    return


@app.cell
def _(chart, df):
    ["Types", type(df), type(chart.dataframe), type(chart.value)]
    return


@app.cell
def _(chart):
    chart.value
    return


@app.cell
def _(chart):
    chart.dataframe
    return


if __name__ == "__main__":
    app.run()
