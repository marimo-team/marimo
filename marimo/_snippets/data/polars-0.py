# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: Lazy Evaluation

        This snippet shows how to use Polars' `lazy()` evaluation for optimized query planning, 
        expression-based operations, and memory-efficient data processing. See example below.
        """
    )
    return


@app.cell
def _():
    import polars as pl
    import numpy as np

    # Create sample DataFrame with numeric data
    df = pl.DataFrame({
        'id': range(1000),
        'category': ['A', 'B', 'C', 'D'] * 250,
        'values': np.arange(0, 2000, 2)
    })

    # Demonstrate lazy evaluation with optimized query
    lazy_query = (
        df.lazy()
        .filter(pl.col('values') > 500)
        .group_by('category')
        .agg([
            pl.col('values').mean().alias('avg_value'),
            pl.col('values').count().alias('count')
        ])
        .sort('avg_value', descending=True)
    )

    # Show optimization plan
    print("Lazy Query Plan:")
    print(lazy_query.explain())

    # Execute lazy query
    result = lazy_query.collect()
    result
    return df, lazy_query, np, pl, result


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
