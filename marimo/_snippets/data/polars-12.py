# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: Lazy Evaluation and Parquet Streaming

        Demonstrates Polars' streaming capabilities for large datasets using lazy evaluation.
        Shows how to efficiently process data without loading entire dataset into memory.

        Example: `pl.scan_parquet("data.parquet").filter(pl.col("date").dt.year() == 2024).collect()`
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

    # Create temporary directory and save files
    temp_dir = Path(tempfile.mkdtemp())
    parquet_path = temp_dir / 'data.parquet'
    df.write_parquet(parquet_path)

    # Demonstrate streaming with lazy evaluation
    streamed = (
        pl.scan_parquet(parquet_path)
        .filter(pl.col('date').dt.year() == 2024)
        .collect()
    )
    streamed
    return (
        Path,
        datetime,
        df,
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
