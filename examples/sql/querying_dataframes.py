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


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Querying dataframes

    This notebook shows how to use SQL to query Python dataframes.

    First, we create a dataframe called `df`.
    """)
    return


@app.cell
def _():
    from vega_datasets import data

    df = data.iris()
    df.head()
    return (df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        f"""
        Next, we **create a SQL cell**.

        Create a SQL cell in one of two ways:

        1. Click the {mo.icon("lucide:database")} `SQL` button at the **bottom of your notebook**
        2. **Right-click** the {mo.icon("lucide:circle-plus")} button to the **left of a cell**, and choose `SQL`.

        In the SQL cell, you can query dataframes in your notebook as if they were tables — just reference them by name.
        """
    )
    return


@app.cell
def _(df, mo):
    result = mo.sql(
        f"""
        SELECT species, mean(petalLength) as meanPetalLength FROM df GROUP BY species ORDER BY meanPetalLength
        """, output=False
    )
    return (result,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The query output is returned to Python as a dataframe (Polars if you have it installed, Pandas otherwise).

    Choose the dataframe name via the **output variable** input in the bottom-left of the cell. If the name starts with an underscore, it won't be made available to other cells.

    In this case, we've named the output `result`.
    """)
    return


@app.cell
def _(result):
    result
    return


if __name__ == "__main__":
    app.run()
