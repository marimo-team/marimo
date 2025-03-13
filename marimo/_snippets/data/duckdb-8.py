# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: Parquet File Ingestion

        This snippet demonstrates how to query Parquet files directly using DuckDB.
        """
    )
    return


@app.cell
def _():
    parquet_path = 'sample-file.parquet'
    return (parquet_path,)


@app.cell
def _(mo, parquet_path):
    query = mo.sql(
        f"""
        SELECT * FROM read_parquet('{parquet_path}')
        LIMIT 10
        """
    )
    return (query,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
