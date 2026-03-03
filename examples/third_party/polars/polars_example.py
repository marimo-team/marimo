# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "altair==5.5.0",
#     "marimo",
#     "numpy==2.0.2",
#     "polars==1.8.2",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Using `Polars` in `marimo`

    > Lightning-fast DataFrame library for Rust and Python
    """)
    return


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import numpy as np
    import altair as alt

    return alt, mo, pl


@app.cell
def _(pl):
    df = pl.read_csv(
        "https://gist.githubusercontent.com/ritchie46/cac6b337ea52281aa23c049250a4ff03/raw/89a957ff3919d90e6ef2d34235e6bf22304f3366/pokemon.csv"
    )
    return (df,)


@app.cell(hide_code=True)
def _(df, mo):
    # get all unique values
    values_1 = df["Type 1"].unique().drop_nulls().to_list()
    values_2 = df["Type 2"].unique().drop_nulls().to_list()

    type_1_filter = mo.ui.dropdown(
        options=values_1,
        label="Type 1",
    )
    type_2_filter = mo.ui.dropdown(
        options=values_2,
        label="Type 2",
    )


    mo.hstack([type_1_filter, type_2_filter], justify="start")
    return type_1_filter, type_2_filter


@app.cell
def _(df, pl, type_1_filter, type_2_filter):
    filtered = df
    if type_1_filter.value:
        filtered = filtered.filter(pl.col("Type 1") == type_1_filter.value)
    if type_2_filter.value:
        filtered = filtered.filter(pl.col("Type 2") == type_2_filter.value)
    return (filtered,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Select points on the chart 👇
    """)
    return


@app.cell(hide_code=True)
def _(alt, filtered, mo):
    _chart = (
        alt.Chart(filtered)
        .mark_circle()
        .encode(
            x="Attack",
            y="Defense",
            size="Total",
            color="Type 1",
            tooltip=["Name", "Total", "Type 1", "Type 2"],
        )
    )

    chart = mo.ui.altair_chart(
        _chart, legend_selection=True, label="Attack vs Defense"
    )
    chart
    return (chart,)


@app.cell
def _(chart, mo):
    mo.ui.table(chart.value)
    return


if __name__ == "__main__":
    app.run()
