# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: Advanced Grouping and Window Functions

        This snippet demonstrates advanced grouping operations in Polars using `group_by()`, 
        window functions, and rolling computations for time series analysis.

        Example: `df.group_by('category').agg([pl.col('value').mean(), pl.col('value').rolling_mean(3)])`
        """
    )
    return


@app.cell
def _():
    import polars as pl
    import numpy as np

    # Create sample data
    n_rows = 30
    df = pl.DataFrame({
        'date': [(pl.datetime(2024, 1, 1) + pl.duration(days=x)) for x in range(n_rows)],
        'category': ['A', 'B', 'C'] * 10,
        'value': np.random.normal(10, 2, n_rows),
        'quantity': np.random.randint(1, 100, n_rows)
    })

    # Advanced grouping and window operations
    result = (
        df.lazy()
        .with_columns([
            # Rolling average
            pl.col('value')
                .rolling_mean(window_size=3)
                .alias('rolling_avg'),
            # Cumulative sum
            pl.col('quantity')
                .cum_sum()
                .over('category')
                .alias('cumsum_by_category')
        ])
        .group_by('category')
        .agg([
            pl.col('value').mean().alias('avg_value'),
            pl.col('quantity').sum().alias('total_quantity')
        ])
        .sort('category')
        .collect()
    )
    result
    return df, n_rows, np, pl, result


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
