# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.4.1",
#     "duckdb==1.1.1",
#     "marimo",
#     "openai==1.51.2",
#     "polars==1.9.0",
#     "pyarrow==17.0.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(r"""
    # SQL Histograms

    This notebook shows how to create a histogram of a column using built-in duckdb aggregate functions.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import duckdb
    import polars
    import pyarrow
    import altair as alt

    return alt, mo


@app.cell
def _():
    URL = "hf://datasets/scikit-learn/Fish/Fish.csv"
    return (URL,)


@app.cell(hide_code=True)
def _(URL, mo):
    mo.md(rf"""First we read the dataset at: **{URL}**""")
    return


@app.cell
def _(URL, mo):
    dataset = mo.sql(
        f"""
        CREATE OR REPLACE VIEW dataset AS
        SELECT *
        FROM read_csv_auto('{URL}');
        FROM dataset
        """
    )
    return


@app.cell
def _(dataset, mo):
    column = mo.ui.dropdown(
        dataset.columns, value=dataset.columns[0], label="Choose a column"
    )
    column
    return (column,)


@app.cell
def _(column, mo):
    histogram = mo.sql(
        f"""
        -- Use the duckdb histogram function
        SELECT bin, count FROM histogram('dataset', {column.value}, bin_count := 10)
        """
    )
    return (histogram,)


@app.cell
def _(mo):
    mo.md(r"""
    Now we will take the histogram result and plot it using [Altair](https://altair-viz.github.io/).
    """)
    return


@app.cell
def _(alt, histogram):
    (
        alt.Chart(histogram)
        .mark_bar()
        .encode(
            x=alt.X("bin:N", sort=alt.EncodingSortField()).axis(labelAngle=20),
            y=alt.Y("count:Q"),
        )
        .properties(width="container")
    )
    return


if __name__ == "__main__":
    app.run()
