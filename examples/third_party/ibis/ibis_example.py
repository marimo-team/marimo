# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "altair==5.4.1",
#     "marimo",
#     "ibis-framework[duckdb,examples]",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(f"""
    # Using `Ibis` in `marimo`

    > Ibis is a Python data analysis library that allows for expressive, efficient, and scalable data manipulation and query processing.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import ibis
    import altair as alt

    return alt, ibis, mo


@app.cell
def _(ibis):
    df = ibis.read_csv(
        "https://gist.githubusercontent.com/ritchie46/cac6b337ea52281aa23c049250a4ff03/raw/89a957ff3919d90e6ef2d34235e6bf22304f3366/pokemon.csv"
    )
    return (df,)


@app.cell
def _(df, mo):
    # get all unique values
    values_1 = df["Type 1"].execute().tolist()
    values_2 = df["Type 2"].execute().tolist()
    # Filter null
    values_2 = [x for x in values_2 if x is not None]

    type_1_filter = mo.ui.dropdown(
        options=values_1,
        label="Type 1",
    )
    type_2_filter = mo.ui.dropdown(
        options=values_2,
        label="Type 2",
    )

    mo.hstack([type_1_filter, type_2_filter])
    return type_1_filter, type_2_filter


@app.cell
def _(alt, filtered, mo):
    # Convert Ibis table to pandas for Altair
    filtered_df = filtered.execute()

    _chart = (
        alt.Chart(filtered_df)
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
def _(df, type_1_filter, type_2_filter):
    filtered = df
    if type_1_filter.value:
        filtered = filtered.filter(df["Type 1"] == type_1_filter.value)
    if type_2_filter.value:
        filtered = filtered.filter(df["Type 2"] == type_2_filter.value)
    return (filtered,)


@app.cell
def _(chart, mo):
    mo.ui.table(chart.value, selection=None)
    return


if __name__ == "__main__":
    app.run()
