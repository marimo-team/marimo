# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "altair",
#     "pandas",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import altair as alt

    return alt, mo, pl


@app.cell
def _(pl):
    df = pl.read_csv(
        "https://gist.githubusercontent.com/netj/8836201/raw/6f9306ad21398ea43cba4f7d537619d0e07d5ae3/iris.csv"
    )
    return (df,)


@app.cell
def _(df, mo):
    table = mo.ui.table(df, label="Iris Data in a table")
    return (table,)


@app.cell
def _(alt, df, mo):
    chart = mo.ui.altair_chart(
        alt.Chart(df)
        .mark_point()
        .encode(x="sepal.length", y="sepal.width", color="variety"),
        label="Iris Data in chart",
    )
    return (chart,)


@app.cell
def _(chart, mo, table):
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
