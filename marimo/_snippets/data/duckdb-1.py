# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: CSV File Ingestion

        This snippet demonstrates how to query CSV files directly using DuckDB.
        """
    )
    return


@app.cell
def _():
    csv_path = 'sample-file.csv'
    return (csv_path,)


@app.cell
def _(csv_path, mo):
    query = mo.sql(
        f"""
        SELECT * FROM read_csv('{csv_path}', AUTO_DETECT=TRUE) 
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
