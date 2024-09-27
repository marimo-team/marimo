# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.11"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md(r"""## Small table""")
    return


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE small_table AS SELECT * FROM range(1000)
        """
    )
    return


@app.cell
def __(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table;
        """
    )
    return


@app.cell
def __(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 10;
        """
    )
    return


@app.cell
def __(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 1000;
        """
    )
    return


@app.cell
def __(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 300;
        """
    )
    return


@app.cell
def __(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 301;
        """
    )
    return


@app.cell
def __(mo, small_table):
    _df = mo.sql(
        f"""
        SELECT * FROM small_table LIMIT 1100;
        """
    )
    return


@app.cell
def __(mo):
    mo.md(r"""## Large table""")
    return


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE large_table AS SELECT * FROM range(30_000);
        """
    )
    return


@app.cell
def __(large_table, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM large_table;
        """
    )
    return


@app.cell
def __(large_table, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM large_table LIMIT 25_000;
        """
    )
    return


@app.cell
def __(large_table, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM large_table LIMIT 20_000;
        """
    )
    return


if __name__ == "__main__":
    app.run()
