# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "polars==1.35.1",
#     "psycopg2-binary==2.9.11",
#     "sqlalchemy==2.0.44",
#     "supabase==2.23.2",
# ]
# ///

import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo
    import polars as pl

    import os


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Supabase SDK
    """)
    return


@app.cell
def _():
    url: str = mo.ui.text(
        value=os.environ.get("SUPABASE_URL", ""), label="Supabase URL"
    )
    key: str = mo.ui.text(
        value=os.environ.get("SUPABASE_KEY", ""),
        label="Supabase Key",
        kind="password",
    )

    mo.hstack([url, key], justify="start", gap=1.5)
    return key, url


@app.cell
def _(Client, create_client, key: str, url: str):
    mo.stop(url.value == "" or key.value == "", mo.md("Please enter URL and Key"))

    supabase_client: Client = create_client(url.value, key.value)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## SQLAlchemy Supabase Client
    """)
    return


@app.cell
def _():
    import sqlalchemy

    _password = os.environ.get("SUPABASE_PASSWORD")
    _host = os.environ.get("SUPABASE_HOST")
    DATABASE_URL = f"postgresql+psycopg2://postgres:{_password}@{_host}:5432/postgres?sslmode=require"
    supabase_engine = sqlalchemy.create_engine(DATABASE_URL)
    return (supabase_engine,)


@app.cell
def _(supabase_engine):
    _df = mo.sql(
        f"""
        SELECT * FROM "storage"."buckets" LIMIT 100
        """,
        engine=supabase_engine
    )
    return


if __name__ == "__main__":
    app.run()
