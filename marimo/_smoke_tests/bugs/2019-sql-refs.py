import marimo

__generated_with = "0.8.4"
app = marimo.App(width="medium")


@app.cell
def __(mo, my_table):
    _df = mo.sql(
        f"""
        SELECT * FROM my_table
        """
    )
    [mo.refs(), mo.defs()]
    return


@app.cell
def __(mo, my_view):
    _df = mo.sql(
        f"""
        SELECT * FROM my_view
        """
    )
    [mo.refs(), mo.defs()]
    return


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPlACE TABLE my_table (a text);
        INSERT INTO my_table (VALUES ('foo'), ('bar'));
        """
    )
    [mo.refs(), mo.defs()]
    return my_table,


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE VIEW my_view AS (SELECT * FROM my_table WHERE a LIKE 'f%o')
        """
    )
    [mo.refs(), mo.defs()]
    return


@app.cell(hide_code=True)
def __():
    import marimo as mo
    import pandas as pd
    return mo, pd


if __name__ == "__main__":
    app.run()
