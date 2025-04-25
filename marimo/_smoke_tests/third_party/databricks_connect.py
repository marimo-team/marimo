

import marimo

__generated_with = "0.13.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    from databricks.connect import DatabricksSession

    spark = DatabricksSession.builder.serverless().getOrCreate()
    return (spark,)


@app.cell
def _(spark):
    df_taxi = spark.read.table("samples.nyctaxi.trips")
    type(df_taxi)
    return (df_taxi,)


@app.cell
def _(df_taxi):
    import narwhals as nw

    # As of 1.35.0, this is currently False
    print(nw.dependencies.is_pyspark_dataframe(df_taxi))
    print(nw.__version__)
    return


@app.cell
def _(df_taxi):
    df_taxi
    return


if __name__ == "__main__":
    app.run()
