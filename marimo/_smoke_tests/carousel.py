# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.13"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import altair as alt
    return alt, mo, pd


@app.cell
def __(pd):
    df = pd.read_csv(
        "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"
    )
    return df,


@app.cell
def __(df, mo):
    table = mo.ui.table(df, label="Iris Data in a table")
    return table,


@app.cell
def __(alt, df, mo):
    chart = mo.ui.altair_chart(
        alt.Chart(df)
        .mark_point()
        .encode(x="sepal_length", y="sepal_width", color="species"),
        label="Iris Data in chart",
    )
    return chart,


@app.cell
def __(chart, mo, table):
    mo.carousel(
        [
            mo.md("# A Presentation on Iris Data"),
            "By the marimo team",
            table,
            chart,
            mo.md("# Thank you!"),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
