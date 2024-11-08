import marimo

__generated_with = "0.9.16"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def __(mo):
    mo.md("""Connect to duckdb [persistent storage](https://duckdb.org/docs/connect/overview.html#persistent-database) using the `ATTACH` command:""")
    return


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        ATTACH 'test.db' as test;
        SHOW ALL TABLES;
        """
    )
    return (test,)


@app.cell
def __(mo, test, test_table):
    _df = mo.sql(
        f"""
        SELECT * FROM test.test_table;
        """
    )
    return


if __name__ == "__main__":
    app.run()
