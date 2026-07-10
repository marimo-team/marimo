# /// script
# requires-python = "==3.10"
# dependencies = [
#     "marimo",
#     "narwhals==1.37.0",
#     "databricks-connect>=16.1.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Using `databcricks_connect`
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from databricks.connect import DatabricksSession

    # This step requires `databricks auth login --host`
    spark = DatabricksSession.builder.serverless().getOrCreate()
    return (spark,)


@app.cell
def _(spark):
    df_taxi = spark.read.table("samples.nyctaxi.trips")
    type(df_taxi)
    return (df_taxi,)


@app.cell
def _(df_taxi):
    df_taxi
    return


if __name__ == "__main__":
    app.run()
