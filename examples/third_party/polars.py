import marimo

__generated_with = "0.1.47"
app = marimo.App(width="full")


@app.cell
def __(mo):
    mo.md(
        f"""
    # Using `Polars` in `marimo`

    > Lightning-fast DataFrame library for Rust and Python

    `pip install polars`
    """
    )
    return


@app.cell
def __():
    import marimo as mo
    import polars as pl
    import numpy as np
    import altair as alt
    return alt, mo, np, pl


@app.cell
def __(pl):
    df = pl.read_csv(
        "https://gist.githubusercontent.com/ritchie46/cac6b337ea52281aa23c049250a4ff03/raw/89a957ff3919d90e6ef2d34235e6bf22304f3366/pokemon.csv"
    )
    return df,


@app.cell
def __(df, mo):
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


    mo.hstack([type_1_filter, type_2_filter])
    return type_1_filter, type_2_filter, values_1, values_2


@app.cell
def __(alt, filtered, mo):
    _chart = (
        alt.Chart(filtered.to_pandas())
        .mark_circle()
        .encode(
            x="Attack",
            y="Defense",
            size="Total",
            color="Type 1",
            tooltip=["Name", "Total", "Type 1", "Type 2"],
        )
    )

    mo.ui.altair_chart(_chart, legend_selection=True, label="Attack vs Defense")
    return


@app.cell
def __(df, pl, type_1_filter, type_2_filter):
    filtered = df
    if type_1_filter.value:
        filtered = filtered.filter(pl.col("Type 1") == type_1_filter.value)
    if type_2_filter.value:
        filtered = filtered.filter(pl.col("Type 2") == type_2_filter.value)
    return filtered,


@app.cell
def __(filtered, mo):
    table = mo.ui.table(filtered)
    table
    return table,


@app.cell
def __(mo, table):
    mo.vstack(
        [
            mo.ui.table(table.value, label="Selected", selection=None),
            table.value,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
