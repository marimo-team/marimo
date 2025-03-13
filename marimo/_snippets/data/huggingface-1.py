# Copyright 2025 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Hugging Face: Datasets with SQL

        Fetch any datasets from [Hugging Face Datasets](https://huggingface.co/datasets) with SQL via [DuckDB](https://duckdb.org/)
        """
    )
    return


@app.cell
def _():
    import duckdb
    import polars as pl
    return duckdb, pl


@app.cell
def _(mo):
    data = mo.sql(
        f"""
        SELECT * FROM "hf://datasets/scikit-learn/Fish/Fish.csv"
        """
    )
    return (data,)


@app.cell
def _(data):
    # Get the SQL result back in Python
    data.describe()
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
