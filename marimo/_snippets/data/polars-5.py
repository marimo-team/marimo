# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: CSV Operations

        Demonstrates Polars' CSV capabilities using `scan_csv()` for 
        streaming large CSV datasets. Shows memory-efficient filtering 
        and aggregation with lazy evaluation.

        Example: `pl.scan_csv("data.csv").filter(pl.col("value") > 500).collect()`
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

    # Create temporary directory and save CSV
    temp_dir = Path(tempfile.mkdtemp())
    csv_path = temp_dir / 'data.csv'
    df.write_csv(csv_path)

    # Demonstrate filtered CSV read
    csv_filtered = (
        pl.scan_csv(csv_path)
        .filter(pl.col('category') == 'A')
        .collect()
    )
    csv_filtered
    return (
        Path,
        csv_filtered,
        csv_path,
        datetime,
        df,
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
