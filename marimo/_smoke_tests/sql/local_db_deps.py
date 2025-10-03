import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        ATTACH 'my_db.db' as my_db;
        """
    )
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE my_db.my_table as (SELECT 42);
        """
    )
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT * FROM my_db.main.my_table LIMIT 100
        """
    )
    return


if __name__ == "__main__":
    app.run()
