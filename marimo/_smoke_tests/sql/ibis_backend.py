# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ibis-framework[datafusion,duckdb]==10.5.0",
#     "marimo",
#     "polars==1.28.1",
#     "pyarrow==20.0.0",
# ]
# ///

import marimo

__generated_with = "0.13.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import pyarrow as pa
    import ibis
    return ibis, mo, pa


@app.cell
def _(ibis, pa):
    con = ibis.datafusion.connect()

    con.create_catalog("my_catalog", force=True)
    con.create_database("my_db", force=True)

    data = pa.table(
        {
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "list": [[1, 2], [3, 4], [5, 6]],
            "dict": [
                {"name": "Alice", "age": 23},
                {"name": "Bob", "age": 45},
                {"name": "Charlie", "age": 4},
            ],
        }
    )
    con.create_table("my_data", obj=data, database="my_db", overwrite=True)
    return (con,)


@app.cell
def _(con, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM my_db.my_data
        """,
        engine=con
    )
    return


if __name__ == "__main__":
    app.run()
