# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.5.0",
#     "datafusion==48.0.0",
#     "ibis-framework[datafusion,duckdb]==10.8.0",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import ibis
    import marimo as mo

    from ibis import _

    ibis.options.interactive = True
    return ibis, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Multi-Catalog Ibis Backend Tests""")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## DuckDB Multi-Catalog with Temp Tables""")
    return


@app.cell
def _(ibis):
    # Create DuckDB connection
    duckdb_con = ibis.duckdb.connect()

    # Create test data using ibis.memtable
    sales_data = ibis.memtable(
        {"product": ["laptop", "mouse", "keyboard"], "price": [1200, 25, 75], "quantity": [10, 100, 50]}
    )

    customer_data = ibis.memtable(
        {"customer_id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"], "region": ["US", "EU", "APAC"]}
    )

    # Create regular table
    duckdb_con.create_table("sales", obj=sales_data, overwrite=True)

    # Create temp table
    duckdb_con.create_table("temp_customers", obj=customer_data, temp=True, overwrite=True)
    return (duckdb_con,)


@app.cell
def _(duckdb_con):
    # Query the regular table using Ibis API with deferred API
    sales_table = duckdb_con.table("sales")
    sales_query = (
        sales_table.mutate(total_value=_.price * _.quantity)
        .select(_.product, _.price, _.quantity, _.total_value)
        .order_by(_.total_value.desc())
    )
    return


@app.cell
def _(duckdb_con):
    # Query the temp table using Ibis API with deferred API
    temp_customers_table = duckdb_con.table("temp_customers")
    temp_query = temp_customers_table.order_by(_.customer_id)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## DuckDB Attached Catalogs""")
    return


@app.cell
def _(duckdb_con, ibis):
    # Attach additional in-memory catalogs using DuckDB's ATTACH
    duckdb_con.raw_sql("ATTACH ':memory:' AS catalog_a")
    duckdb_con.raw_sql("ATTACH ':memory:' AS catalog_b")

    # Create tables in different catalogs using ibis API
    inventory_data = ibis.memtable({"product": ["laptop", "mouse", "keyboard"], "stock": [50, 200, 100]})

    orders_data = ibis.memtable({"order_id": [1, 2, 3], "product": ["laptop", "mouse", "laptop"], "quantity": [2, 1, 1]})

    # Create tables in specific catalogs using dot notation
    duckdb_con.create_table("inventory", obj=inventory_data, database="catalog_a.main", overwrite=True)
    duckdb_con.create_table("orders", obj=orders_data, database="catalog_b.main", overwrite=True)
    return


@app.cell
def _(duckdb_con):
    # Cross-catalog query using Ibis API with deferred API
    orders_table = duckdb_con.table("orders", database="catalog_b.main")
    inventory_table = duckdb_con.table("inventory", database="catalog_a.main")

    cross_catalog_query = (
        orders_table.join(inventory_table, _.product == inventory_table.product)
        .select(_.order_id, _.product, _.quantity, inventory_table.stock)
        .order_by(_.order_id)
    )

    cross_catalog_query
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## DataFusion Backend""")
    return


@app.cell
def _(ibis):
    # Create DataFusion connection
    datafusion_con = ibis.datafusion.connect()

    # Create test data using ibis.memtable
    products_data = ibis.memtable(
        {
            "product_id": [1, 2, 3],
            "name": ["Widget A", "Widget B", "Widget C"],
            "category": ["Electronics", "Tools", "Electronics"],
        }
    )

    # Create table
    datafusion_con.create_table("products", obj=products_data, overwrite=True)
    return (datafusion_con,)


@app.cell
def _(datafusion_con):
    # Query using Ibis API with deferred API
    products_table = datafusion_con.table("products")
    electronics_query = (
        products_table.filter(_.category == "Electronics").select(_.product_id, _.name, _.category).order_by(_.product_id)
    )

    datafusion_con.create_table("electronics", electronics_query, overwrite=True)
    return


if __name__ == "__main__":
    app.run()
