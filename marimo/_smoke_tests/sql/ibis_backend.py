# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "grpcio==1.71.0",
#     "grpcio-status==1.71.0",
#     "ibis-framework[datafusion,duckdb,pyspark]==10.5.0",
#     "marimo",
#     "polars==1.28.1",
#     "protobuf==6.30.2",
#     "pyarrow==20.0.0",
#     "pyspark==3.5.5",
#     "setuptools==80.1.0",
# ]
# ///

import marimo

__generated_with = "0.13.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import pyarrow as pa
    import ibis
    return ibis, mo, pa


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## DataFusion Connection""")
    return


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
    return con, data


@app.cell
def _(con, mo, my_data, my_db):
    _df = mo.sql(
        f"""
        SELECT * FROM my_db.my_data
        """,
        engine=con
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## PySpark Connection

    Spin up a spark cluster using docker. We will use Spark Connect to communicate with this cluster.
    ```shell
    docker run -p 15002:15002 --name spark-connect \
      # -v /Users/my_name/Development/marimo:/mounted_data \
      bitnami/spark:3.5.0 spark-submit \
      --class org.apache.spark.sql.connect.service.SparkConnectServer \
      --packages org.apache.spark:spark-connect_2.12:3.5.0 \
      --conf spark.connect.grpc.binding.port=15002 \
      --conf spark.connect.grpc.arrow.maxBatchSize=50000
    ```

    Notice I have commented out mounting a local volume, you can opt to ignore that line. Include this to read your local filesystem.
    """
    )
    return


@app.cell
def _(ibis):
    from pyspark.sql import SparkSession, Row
    from pyspark.sql.functions import col
    from datetime import date, datetime

    # Create a SparkSession
    session = SparkSession.builder.remote("sc://localhost:15002").getOrCreate()
    pyspark_conn = ibis.pyspark.connect(session)
    return (pyspark_conn,)


@app.cell
def _(data, pyspark_conn):
    # pyspark_conn.read_csv("/mounted_data/order_details.csv").to_polars()
    pyspark_conn.create_table("my_data", obj=data, overwrite=True)
    return


@app.cell
def _(mo, my_data, pyspark_conn):
    _df = mo.sql(
        f"""
        SELECT * FROM my_data
        """,
        engine=pyspark_conn
    )
    return


if __name__ == "__main__":
    app.run()
