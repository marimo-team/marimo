# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: JSON File Ingestion

        This snippet demonstrates how to query JSON files directly using DuckDB.
        """
    )
    return


@app.cell
def _():
    json_path = 'sample-file.json'
    return (json_path,)


@app.cell
def _(json_path, mo):
    query = mo.sql(
        f"""
        SELECT * FROM read_json_auto('{json_path}')
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
