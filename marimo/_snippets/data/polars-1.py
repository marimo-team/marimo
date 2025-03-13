# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Polars: Rolling Averages and Z-Score Calculations
        
        This snippet shows advanced column operations in Polars using `rolling_mean()`, `over()` aggregations, 
        and type casting with the expression API.
        """
    )
    return


@app.cell
def __():
    import polars as pl
    from datetime import datetime, timedelta
    
    # Create sample DataFrame with proper datetime
    df = pl.DataFrame({
        'id': range(1000),
        'value': [1.5, 2.5, 3.5] * 333 + [1.5],
        'category': ['A', 'B', 'C'] * 333 + ['A'],
        'date': [(datetime(2024, 1, 1) + timedelta(days=x)) for x in range(1000)]
    })
    
    # Demonstrate advanced expressions
    result = (
        df.lazy()
        .with_columns([
            pl.col('value').sum().over('category').alias('category_sum'),
            pl.col('value').rolling_mean(3).alias('rolling_avg'),
            pl.col('date').dt.month().cast(pl.Categorical).alias('month'),
            ((pl.col('value') - pl.col('value').mean()) / 
             pl.col('value').std()).alias('zscore')
        ])
        .collect()
    )
    
    return df, result, pl


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
