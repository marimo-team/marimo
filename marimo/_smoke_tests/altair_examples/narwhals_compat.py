import marimo

__generated_with = "0.9.9"
app = marimo.App(width="medium")


@app.cell
def __():
    import altair as alt
    import pandas as pd
    import polars as pl

    import marimo as mo

    return alt, mo, pd, pl


@app.cell
def __(mo, pd, pl):
    url = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"

    df_selection = mo.ui.dropdown(
        {"pandas": pd.read_csv(url), "polars": pl.read_csv(url), "url": url},
        value="polars",
    )
    df_selection
    return df_selection, url


@app.cell
def __(alt, df_selection, mo):
    df = df_selection.value
    chart = mo.ui.altair_chart(
        alt.Chart(df)
        .mark_point()
        .encode(x="sepal_length:Q", y="sepal_width:Q")
    )
    chart
    return chart, df


@app.cell
def __(chart):
    chart.data
    return


@app.cell
def __(chart, df):
    ["Types", type(df), type(chart.dataframe), type(chart.value)]
    return


@app.cell
def __(chart):
    chart.value
    return


@app.cell
def __(chart):
    chart.dataframe
    return


if __name__ == "__main__":
    app.run()
