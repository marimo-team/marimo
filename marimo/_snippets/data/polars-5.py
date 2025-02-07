# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: Efficient IO Operations

        Demonstrates Polars' powerful IO capabilities:

        This snippet demonstrates efficient IO operations in Polars using `scan_parquet()` and `scan_csv()` for 
        streaming large datasets. Shows memory-efficient filtering and aggregation with lazy evaluation.
        
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

    # Create sample data with various types
    df = pl.DataFrame({
        'id': range(1000),
        'date': [(datetime.date(2024, 1, 1) + datetime.timedelta(days=x % 366)) for x in range(1000)],
        'category': ['A', 'B', 'C'] * 333 + ['A'],
        'value': range(1000)
    })

    # Create temporary directory for demo
    temp_dir = Path(tempfile.mkdtemp())

    # 1. Parquet operations with partitioning
    parquet_path = temp_dir / 'data.parquet'
    df.write_parquet(
        parquet_path,
        compression='snappy',
        use_pyarrow=True
    )

    # 2. CSV operations for comparison
    csv_path = temp_dir / 'data.csv'
    df.write_csv(csv_path)

    # 3. Demonstrate different reading techniques
    # a. Filtered parquet read
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

    # b. Filtered CSV read
    csv_filtered = (
        pl.scan_csv(csv_path)
        .filter(pl.col('category') == 'A')
        .collect()
    )

    # c. Streaming large files with lazy evaluation
    streamed = (
        pl.scan_parquet(parquet_path)
        .filter(pl.col('date').dt.year() == 2024)
        .collect()
    )
    parquet_filtered, csv_filtered, streamed
    return (
        Path,
        csv_filtered,
        csv_path,
        datetime,
        df,
        parquet_filtered,
        parquet_path,
        pl,
        streamed,
        temp_dir,
        tempfile,
    )


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
