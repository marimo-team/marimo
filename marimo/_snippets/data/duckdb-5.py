# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: Join Operations & Multi-Table Queries

        This snippet demonstrates how to perform JOIN operations between 
        two DataFrames using DuckDB's SQL engine within marimo.
        """
    )
    return


@app.cell
def _():
    import polars as pl
    # Create two sample DataFrames to join
    df1 = pl.DataFrame({
        'id': [1, 2, 3, 4],
        'value1': ['A', 'B', 'C', 'D']
    })
    df2 = pl.DataFrame({
        'id': [3, 4, 5, 6],
        'value2': ['X', 'Y', 'Z', 'W']
    })
    return df1, df2, pl


@app.cell
def _(df1, df2, mo):
    join_df = mo.sql(
        f"""
        SELECT a.id, a.value1, b.value2
        FROM df1 a
        INNER JOIN df2 b ON a.id = b.id
        """
    )
    return (join_df,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
