# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: Basic SQL Querying and DataFrame Integration

        This snippet demonstrates how to use `marimo`'s SQL cells to execute 
        queries against a local Pandas DataFrame. We leverage parameterized 
        queries through f-string interpolation.
        """
    )
    return


@app.cell
def _():
    import polars as pl
    # Create a sample DataFrame
    data = {
        'id': list(range(1, 11)),
        'value': [x * 10 for x in range(1, 11)]
    }
    df = pl.DataFrame(data)
    return data, df, pl


@app.cell
def _():
    max_rows = 5
    return (max_rows,)


@app.cell
def _(df, max_rows, mo):
    limited_df = mo.sql(
        f"""
        SELECT * FROM df LIMIT {max_rows}
        """
    )
    return (limited_df,)


@app.cell
def _(df, max_rows, mo):
    result_df = mo.sql(
        f"""
        SELECT * FROM df WHERE value > {max_rows * 10}
        """
    )
    return (result_df,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
