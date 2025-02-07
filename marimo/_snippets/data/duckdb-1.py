# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: File Ingestion & External Data Sources

        This snippet shows how to query external data files using DuckDB.
        Examples include reading from CSV, JSON and Parquet files directly via SQL.
        """
    )
    return


@app.cell
def _():
    # Example file paths (replace with actual paths or URLs in practice)
    csv_path = 'sample.csv'
    json_path = 'sample.json'
    parquet_path = 'sample.parquet'
    return csv_path, json_path, parquet_path


@app.cell
def _(csv_path, mo):
    csv_df = mo.sql(
        f"""
        SELECT * FROM read_csv('{csv_path}', AUTO_DETECT=TRUE) LIMIT 10
        """
    )
    return (csv_df,)


@app.cell
def _(mo, parquet_path):
    parquet_df = mo.sql(
        f"""
        SELECT * FROM read_parquet('{parquet_path}') LIMIT 10
        """
    )
    return (parquet_df,)


@app.cell
def _(json_path, mo):
    json_df = mo.sql(
        f"""
        SELECT * FROM read_json('{json_path}') LIMIT 10
        """
    )
    return (json_df,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
