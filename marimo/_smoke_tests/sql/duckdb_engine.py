import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import duckdb

    connection_one = duckdb.connect("one.db")
    connection_two = duckdb.connect("two.db")
    return connection_one, connection_two


@app.cell
def _(connection_one, mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE numbers AS 
        SELECT * FROM range(1, 101) AS n;
        """,
        engine=connection_one
    )
    return


@app.cell
def _(connection_two, mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE other_numbers AS 
        SELECT * FROM range(1, 101) AS n;
        """,
        engine=connection_two
    )
    return


@app.cell
def _(connection_one, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM duckdb_tables();
        """,
        engine=connection_one
    )
    return


@app.cell
def _(connection_two, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM duckdb_tables();
        """,
        engine=connection_two
    )
    return


if __name__ == "__main__":
    app.run()
