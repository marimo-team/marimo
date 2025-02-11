# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: Advanced SQL with Aggregations & Window Functions

        This snippet demonstrates advanced SQL queries including group-by aggregations 
        and window functions (e.g., cumulative sums) using DuckDB.
        """
    )
    return


@app.cell
def _():
    import polars as pl
    # Create sample DataFrame
    data = {
        'group': ['A', 'A', 'B', 'B', 'C', 'C'],
        'value': [10, 15, 20, 25, 30, 35]
    }
    df = pl.DataFrame(data)
    return data, df, pl


@app.cell
def _(df, mo):
    agg_df = mo.sql(
        f"""
        SELECT 
            "group", 
            CAST(AVG(value) AS FLOAT) as avg_value 
        FROM df 
        GROUP BY "group"
        """
    )
    return (agg_df,)


@app.cell
def _(df, mo):
    window_df = mo.sql(
        f"""
        SELECT 
            *,
            CAST(SUM(value) OVER (PARTITION BY "group" ORDER BY value) AS FLOAT) as cumulative_sum
        FROM df
        """
    )
    return (window_df,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
