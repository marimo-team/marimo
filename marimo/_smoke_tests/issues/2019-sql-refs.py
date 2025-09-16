import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT * FROM my_table
        """
    )
    [mo.refs(), mo.defs()]
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT * FROM my_view
        """
    )
    [mo.refs(), mo.defs()]
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPlACE TABLE my_table (a text);
        INSERT INTO my_table (VALUES ('foo'), ('bar'));
        """
    )
    [mo.refs(), mo.defs()]
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE VIEW my_view AS (SELECT * FROM my_table WHERE a LIKE 'f%o')
        """
    )
    [mo.refs(), mo.defs()]
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import pandas as pd
    return (mo,)


if __name__ == "__main__":
    app.run()
