# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "duckdb==1.1.1",
#     "marimo",
#     "polars==1.18.0",
#     "pyarrow==18.1.0",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Read Parquet

    This notebook shows how to read a Parquet file from a local file or a URL into an in-memory table.
    """)
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import polars as pl

    pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]}).write_parquet("data.parquet")
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Reading from a Parquet file is as easy as `SELECT * from "data.parquet"`, where `data.parquet` is the path or URL to your parquet file.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.accordion(
        {
            "Tip: Creating SQL Cells": mo.md(
                f"""
                Create a SQL cell in one of two ways:

                1. Click the {mo.icon("lucide:database")} `SQL` button at the **bottom of your notebook**
                2. **Right-click** the {mo.icon("lucide:circle-plus")} button to the **left of a cell**, and choose `SQL`.

                In the SQL cell, you can query dataframes in your notebook as if
                they were tables — just reference them by name.
                """
            )
        }
    )
    return


@app.cell
def _(mo):
    result = mo.sql(
        f"""
        -- Tip: you can also specify the data files using a glob, such as '/path/to/*.parquet'
        -- or '/path/**/to/*.parquet'
        SELECT * FROM 'data.parquet'
        """, output=False
    )
    return (result,)


@app.cell(hide_code=True)
def _(mo):
    mo.accordion(
        {
            "Tip: Query output": mo.md(
                r"""
                The query output is returned to Python as a dataframe (Polars if you have it installed, Pandas otherwise).

                Choose the dataframe name via the **output variable** input in the bottom-left
                of the cell. If the name starts with an underscore, it won't be made available
                to other cells. In this case, we've named the output `result`.
                """
            )
        }
    )
    return


@app.cell
def _(result):
    result
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Create an in-memory table from a Parquet file

    You can also create a table from a Parquet file, so you can easily query it in subsequent cells. This table will appear in marimo's data sources panel.
    """)
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE myTable AS SELECT * FROM 'data.parquet'
        """
    )
    return


@app.cell
def _(mo, mytable):
    _df = mo.sql(
        f"""
        SELECT * FROM myTable
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Advanced usage
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    To customize how your parquet file is read, use [duckdb's `read_parquet` function](https://duckdb.org/docs/data/parquet/overview.html).
    """)
    return


if __name__ == "__main__":
    app.run()
