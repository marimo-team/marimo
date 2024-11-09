import marimo

__generated_with = "0.9.16"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        ATTACH 'my_db.db' as my_db;
        """
    )
    return (my_db,)


@app.cell
def __(mo):
    _df = mo.sql(
        f"""
        CREATE OR REPLACE TABLE my_db.my_table as (SELECT 42);
        """
    )
    return


@app.cell
def __(mo, my_db, my_table):
    _df = mo.sql(
        f"""
        SELECT * FROM my_db.main.my_table LIMIT 100
        """
    )
    return


if __name__ == "__main__":
    app.run()
