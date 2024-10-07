# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "duckdb==1.1.1",
#     "marimo",
#     "pandas==2.2.3",
#     "requests==2.32.3",
# ]
# ///

import marimo

__generated_with = "0.9.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        # Connect to Postgres

        You can use marimo's SQL cells to read from and write to Postgres databases.

        The first step is to attach a Postgres database, which we do below.

        _For advanced usage, see [duckdb's documentation](https://duckdb.org/docs/extensions/postgres)._
        """
    )
    return


@app.cell(hide_code=True)
def __():
    import marimo as mo


    def download_sample_data():
        import os
        import requests

        url = "https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
        filename = "Chinook_Sqlite.sqlite"
        if not os.path.exists(filename):
            print("Downloading the Chinook database ...")
            response = requests.get(url)
            with open(filename, "wb") as f:
                f.write(response.content)


    download_sample_data()
    return download_sample_data, mo


@app.cell(hide_code=True)
def __(mo):
    mo.accordion(
        {
            "Tip: Creating SQL Cells": mo.md(
                f"""
                Create a SQL cell in one of two ways:

                1. Click the {mo.icon("lucide:database")} `SQL` button at the **bottom of your notebook**
                2. **Right-click** the {mo.icon("lucide:circle-plus")} button to the **left of a cell**, and choose `SQL`.

                In the SQL cell, you can query dataframes in your notebook as if
                they were tables — just reference them by name.
                """
            )
        }
    )
    return


@app.cell
def __():
    import os

    PASSWORD = os.getenv("PGPASSWORD", "mysecretpassword")
    return PASSWORD, os


@app.cell
def __(PASSWORD, mo):
    _df = mo.sql(
        f"""
        -- Boilerplate: detach the database so this cell works when you re-run it
        DETACH DATABASE IF EXISTS db;

        -- Attach the database; omit READ_ONLY if you want to write to the database.
        -- The ATTACH command accepts either a libpq connection string (as below) or a PostgreSQL URI.
        -- You can filter to specific schemas, as we do below.
        ATTACH 'dbname=postgres user=postgres host=127.0.0.1 password={PASSWORD}' as db (
            TYPE POSTGRES, READ_ONLY, SCHEMA 'public'
        );

        -- View tables in the public schema
        SELECT table_name FROM INFORMATION_SCHEMA.TABLES;
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""Once the database is attached, you can query it with SQL.""")
    return


@app.cell
def __(db, mo, test_table):
    _df = mo.sql(
        f"""
        -- Query your tables! This assumes a database with schema public and a sample table called test_table.
        SELECT * FROM db.public.test_table;
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        f"""
        You can explore the schemas of all your tables at a glance in the **data sources panel**: click
        the {mo.icon("lucide:database")} icon in the left sidebar to open it.
        """
    )
    return


if __name__ == "__main__":
    app.run()
