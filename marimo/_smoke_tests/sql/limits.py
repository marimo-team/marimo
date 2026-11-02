# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    ## Small table
    """)


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE small_table AS SELECT * FROM range(1000)
        """
    )


@app.cell
def _(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table;
        """
    )


@app.cell
def _(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 10;
        """
    )


@app.cell
def _(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 1000;
        """
    )


@app.cell
def _(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 300;
        """
    )


@app.cell
def _(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 301;
        """
    )


@app.cell
def _(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 1100;
        """
    )


@app.cell
def _(mo):
    mo.md(r"""
    ## Large table
    """)


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE large_table AS SELECT * FROM range(30_000);
        """
    )


@app.cell
def _(large_table, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM large_table;
        """
    )


@app.cell
def _(large_table, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM large_table LIMIT 25_000;
        """
    )


@app.cell
def _(large_table, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM large_table LIMIT 20_000;
        """
    )


if __name__ == "__main__":
    app.run()
