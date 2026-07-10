# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "polars==1.27.1",
#     "pyarrow==19.0.1",
#     "pyiceberg==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os

    return mo, os


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # PyIceberg REST Catalog

    This notebook shows you how to connect to an Apache Iceberg data catalog over REST.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    /// details | Create a new catalog with Cloudflare

    1. Create a Cloudflare account
    2. Go to <https://developers.cloudflare.com/r2/data-catalog/>


    ///
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Connect to a data catalog
    """)
    return


@app.cell(hide_code=True)
def _(mo, os):
    warehouse_input = mo.ui.text(
        label="Warehouse", value=os.environ.get("DATA_CATALOG_WAREHOUSE", "")
    )
    token_input = mo.ui.text(
        label="Token",
        value=os.environ.get("DATA_CATALOG_TOKEN", ""),
        kind="password",
    )
    catalog_input = mo.ui.text(
        label="Catalog URI", value=os.environ.get("DATA_CATALOG_URI", "")
    )
    mo.vstack([warehouse_input, token_input, catalog_input])
    return catalog_input, token_input, warehouse_input


@app.cell(hide_code=True)
def _(catalog_input, mo, token_input, warehouse_input):
    mo.stop(not warehouse_input.value, mo.md("Missing Warehouse"))
    mo.stop(not token_input.value, mo.md("Missing Token"))
    mo.stop(not catalog_input.value, mo.md("Missing Catalog UI"))

    WAREHOUSE = warehouse_input.value
    TOKEN = token_input.value
    CATALOG_URI = catalog_input.value
    return CATALOG_URI, TOKEN, WAREHOUSE


@app.cell
def _(CATALOG_URI, TOKEN, WAREHOUSE):
    import pyarrow as pa
    from pyiceberg.catalog.rest import RestCatalog
    from pyiceberg.exceptions import NamespaceAlreadyExistsError

    # Connect to R2 Data Catalog
    catalog = RestCatalog(
        name="my_catalog",
        warehouse=WAREHOUSE,
        uri=CATALOG_URI,
        token=TOKEN,
    )

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
    return df, table


@app.cell
def _(mo):
    add_button = mo.ui.run_button(label="Add data")
    clear_button = mo.ui.run_button(label="Clear data")
    mo.hstack([add_button, clear_button])
    return add_button, clear_button


@app.cell
def _(add_button, clear_button, df, table):
    if add_button.value:
        table.append(df)
    if clear_button.value:
        table.delete()
    table.to_polars().collect()
    return


if __name__ == "__main__":
    app.run()
