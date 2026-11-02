import marimo

__generated_with = "0.25.2"
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


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE my_db.my_table as (SELECT 42);
        """
    )


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SELECT * FROM my_db.main.my_table LIMIT 100
        """
    )


if __name__ == "__main__":
    app.run()
