# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "duckdb==1.1.1",
#     "marimo",
#     "pandas==2.2.3",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.9.1"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        # Parametrizing SQL Queries

        This notebook shows parametrize SQL queries with Python values, using Python f-string interpolation.

        First, we create a dataframe called `df`.
        """
    )
    return


@app.cell
def __():
    from vega_datasets import data

    df = data.iris()
    df
    return data, df


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""Next, we create a dropdown that selects the iris species.""")
    return


@app.cell
def __(mo):
    species_dropdown = mo.ui.dropdown(["setosa", "versicolor", "virginica"], value="setosa")
    species_dropdown
    return (species_dropdown,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        """
        Next, we **create a SQL cell** that filters the table to the selected species.
        
        Notice that we can reference the Python variable `species_dropdown` in our query
        using **curly braces**. This is because marimo represents SQL queries as Python
        f-strings. 
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
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
def __(df, mo, species_dropdown):
    result = mo.sql(
        f"""
        SELECT * FROM df where species == '{species_dropdown.value}'
        """, output=False
    )
    return (result,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        The query output is returned to Python as a dataframe (Polars if you have it installed, Pandas otherwise).

        Choose the dataframe name via the **output variable** input in the bottom-left
        of the cell. If the name starts with an underscore, it won't be made available
        to other cells. In this case, we've named the output `result`.

        Try changing the selected species in the `species_dropdown`, and watch how the query result changes.
        """
    )
    return


@app.cell
def __(result):
    result
    return


if __name__ == "__main__":
    app.run()
