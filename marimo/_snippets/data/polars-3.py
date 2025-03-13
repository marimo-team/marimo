# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: High-Performance Joins and Aggregations

        This snippet shows efficient join operations in Polars using `lazy()` evaluation. 
        Demonstrates joining DataFrames with different strategies, aggregating results, 
        and applying window functions for analysis.
        """
    )
    return


@app.cell
def _():
    import polars as pl

    # Create sample DataFrames
    df1 = pl.DataFrame({
        'id': range(1000),
        'value': [1.5, 2.5, 3.5] * 333 + [1.5],
        'category': ['A', 'B', 'C'] * 333 + ['A']
    })

    df2 = pl.DataFrame({
        'id': range(500, 1500),  # Overlapping and non-overlapping IDs
        'other_value': range(1000),
        'category': ['B', 'C', 'D'] * 333 + ['B']
    })

    # 1. Basic join with aggregations
    basic_join = (
        df1.lazy()
        .join(
            df2.lazy(),
            on='id',
            how='left'
        )
        .group_by('category')
        .agg([
            pl.col('value').mean().alias('avg_value'),
            pl.col('other_value').mean().alias('avg_other_value'),
            pl.col('id').count().alias('count')
        ])
        .sort('category')
        .collect()
    )

    # 2. Advanced join with window functions
    window_ops = (
        df1.lazy()
        .join(
            df2.lazy(),
            on='id',
            how='left'
        )
        .with_columns([
            # Window functions
            pl.col('value').sum().over('category').alias('category_total'),
            pl.col('value').mean().over('category').alias('category_avg'),
            pl.col('value').rank().over('category').alias('rank_in_category'),
            # Rolling calculations
            pl.col('value')
                .rolling_mean(window_size=3)
                .over('category')
                .alias('rolling_avg')
        ])
        .sort(['category', 'id'])
        .collect()
    )
    basic_join, window_ops
    return basic_join, df1, df2, pl, window_ops


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
