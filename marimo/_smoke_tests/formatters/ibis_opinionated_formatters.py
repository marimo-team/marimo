# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "ibis-framework[duckdb]==11.0.0",
# ]
# ///

import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium", auto_download=["html", "ipynb"])


@app.cell
def _():
    import ibis
    import marimo as mo
    return ibis, mo


@app.cell
def _(ibis):
    ibis.options.interactive = True

    con = ibis.duckdb.connect()

    con.raw_sql("INSTALL httpfs; LOAD httpfs;")

    con.raw_sql("SET s3_region='us-west-2'")
    return (con,)


@app.cell
def _(con):
    path = "s3://overturemaps-us-west-2/release/2025-10-22.0/theme=base/type=infrastructure/*.parquet"

    t = con.read_parquet(path, hive_partitioning=True, filename=True)
    return (t,)


@app.cell
def _(t):
    t.schema()
    return


@app.cell
def _(t):
    t._find_backends()
    return


@app.cell
def _(t):
    # This should render the opinionated table, somewhat fast, without fetching the full dataframe into memory
    t
    return


@app.cell
def _(t):
    # This should render the opinionated table, somewhat fast, without fetching the full dataframe into memory
    t.limit(10)
    return


@app.cell
def _(mo, t):
    # Should show a plain HTML table from ibis
    mo.plain(t)
    return


@app.cell
def _():
    # t
    return


if __name__ == "__main__":
    app.run()
