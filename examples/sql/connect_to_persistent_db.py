import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Connect to duckdb [persistent storage](https://duckdb.org/docs/connect/overview.html#persistent-database) using the `ATTACH` command:
    """)
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        ATTACH 'test.db' as test;
        SHOW ALL TABLES;
        """
    )
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT * FROM test.test_table;
        """
    )
    return


if __name__ == "__main__":
    app.run()
