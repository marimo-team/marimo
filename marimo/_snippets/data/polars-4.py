# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: Dynamic Time Windows and Aggregations

        This snippet shows time series operations in Polars using `dt` expressions for 
        parsing and formatting, dynamic time windows with `group_by_dynamic()`, 
        and timezone-aware calculations.
        """
    )
    return


@app.cell
def _():
    import polars as pl
    import numpy as np
    from datetime import datetime, timedelta

    # Create time series data
    dates = [datetime(2024, 1, 1) + timedelta(hours=x) for x in range(1000)]
    df = pl.DataFrame({
        'timestamp': dates,
        'value': np.random.normal(0, 1, 1000),
        'category': ['A', 'B'] * 500
    })

    # Time series operations
    result = (
        df.lazy()
        .with_columns([
            # Convert to timezone-aware datetime
            pl.col('timestamp').dt.replace_time_zone('UTC').alias('timestamp_utc'),
            # Extract components
            pl.col('timestamp').dt.hour().alias('hour'),
            pl.col('timestamp').dt.weekday().alias('weekday')  # Fixed: using weekday instead of day_of_week
        ])
        .group_by_dynamic(
            'timestamp',
            every='1d',  # Daily windows
            closed='left'
        )
        .agg([
            pl.col('value').mean().alias('daily_avg'),
            pl.col('value').std().alias('daily_std'),
            pl.col('value').count().alias('count')
        ])
        .sort('timestamp')
        .collect()
    )
    result
    return dates, datetime, df, np, pl, result, timedelta


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
