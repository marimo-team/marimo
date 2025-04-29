# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "polars==1.28.1",
#     "pyarrow==20.0.0",
#     "pyiceberg[sql-sqlite]==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.13.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pyarrow as pa
    from pyiceberg.catalog import load_catalog
    return load_catalog, pa


@app.cell
def _(load_catalog):
    warehouse_path = "/tmp/"
    catalog = load_catalog(
        "default",
        **{
            "type": "sql",
            "uri": f"sqlite:///{warehouse_path}/pyiceberg_catalog.db",
            "warehouse": f"file://{warehouse_path}",
        },
    )
    return (catalog,)


@app.cell
def _(catalog, pa):
    # Create default namespace
    catalog.create_namespace_if_not_exists("default")

    # Create simple PyArrow table
    df = pa.table(
        {
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
        }
    )

    # Create an Iceberg table
    test_table = ("default", "my_table")
    table = catalog.create_table_if_not_exists(
        test_table,
        schema=df.schema,
    )
    table.overwrite(df)
    return (test_table,)


@app.cell
def _(catalog, test_table):
    catalog.load_table(test_table).to_polars().collect()
    return


if __name__ == "__main__":
    app.run()
