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

__generated_with = "0.9.4"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    mo.md(
        r"""
        # SQL Histograms

        This notebook shows how to create a histogram of a column using built-in duckdb aggregate functions.
        """
    )
    return


@app.cell
def __():
    import marimo as mo
    import duckdb
    import polars
    import pyarrow
    import altair as alt
    return alt, duckdb, mo, polars, pyarrow


@app.cell
def __():
    URL = "hf://datasets/scikit-learn/Fish/Fish.csv"
    return (URL,)


@app.cell(hide_code=True)
def __(URL, mo):
    mo.md(rf"""First we read the dataset at: **{URL}**""")
    return


@app.cell
def __(URL, dataset, mo):
    dataset = mo.sql(
        f"""
        CREATE OR REPLACE VIEW dataset AS
        SELECT *
        FROM read_csv_auto('{URL}');
        FROM dataset
        """
    )
    return (dataset,)


@app.cell
def __(dataset, mo):
    column = mo.ui.dropdown(
        dataset.columns, value=dataset.columns[0], label="Choose a column"
    )
    column
    return (column,)


@app.cell
def __(column, mo):
    histogram = mo.sql(
        f"""
        -- Use the duckdb histogram function
        SELECT bin, count FROM histogram('dataset', {column.value}, bin_count := 10)
        """
    )
    return (histogram,)


@app.cell
def __(mo):
    mo.md(r"""Now we will take the histogram result and plot it using [Altair](https://altair-viz.github.io/).""")
    return


@app.cell
def __(alt, histogram):
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
