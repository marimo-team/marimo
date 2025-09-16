# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "connectorx==0.4.1",
#     "marimo",
#     "polars==1.20.0",
#     "pyarrow==19.0.0",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    import os
    import pyarrow
    import connectorx

    uri = os.environ.get("DATABASE_URL")
    return pl, uri


@app.cell
def _(mo, pl, uri):
    mo.stop(not uri)
    query = "SELECT * FROM pg_catalog.pg_tables;"

    df = pl.read_database_uri(query=query, uri=uri)
    df
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
