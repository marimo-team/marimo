# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: Parquet Operations

        Demonstrates Polars' Parquet capabilities using `scan_parquet()` for 
        streaming large Parquet datasets. Shows memory-efficient filtering 
        and aggregation with lazy evaluation.

        Example: `pl.scan_parquet("data.parquet").filter(pl.col("value") > 500).collect()`
        """
    )
    return


@app.cell
def _():
    import polars as pl
    import tempfile
    from pathlib import Path
    import datetime

    # Create sample data
    df = pl.DataFrame({
        'date': [(datetime.date(2024, 1, 1) + datetime.timedelta(days=x % 366)) for x in range(1000)],
        'category': ['A', 'B', 'C'] * 333 + ['A'],
        'value': range(1000)
    })

    # Create temporary directory and save Parquet
    temp_dir = Path(tempfile.mkdtemp())
    parquet_path = temp_dir / 'data.parquet'
    df.write_parquet(
        parquet_path,
        compression='snappy',
        use_pyarrow=True
    )

    # Demonstrate filtered parquet read with aggregation
    parquet_filtered = (
        pl.scan_parquet(parquet_path)
        .filter(pl.col('value') > 500)
        .group_by('category')
        .agg([
            pl.col('value').mean().alias('avg_value'),
            pl.col('value').count().alias('count')
        ])
        .collect()
    )
    parquet_filtered
    return (
        Path,
        datetime,
        df,
        parquet_filtered,
        parquet_path,
        pl,
        temp_dir,
        tempfile,
    )


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
