# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "duckdb==1.1.1",
#     "marimo",
#     "numpy==2.2.6",
#     "pandas==2.2.3",
#     "polars==1.18.0",
#     "pyarrow==18.1.0",
#     "sqlglot==26.19.0",
# ]
# ///

import marimo

__generated_with = "0.13.11"
app = marimo.App(width="full")


@app.cell
def _():
    import os

    import duckdb
    import marimo as mo
    return duckdb, mo, os


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    # Database explorer

    This notebook lets you explore the contents of a database. Start by providing a database URL.
    """
    )
    return


@app.cell
def _(mo, os):
    database_url = mo.ui.text(
        label="Database URL",
        full_width=True,
        value=os.environ.get("DATABASE_URL", ""),
    )
    database_url
    return (database_url,)


@app.cell
def _(database_url, duckdb):
    if database_url.value:
        duckdb.sql(
            f"""
                INSTALL postgres; 
                LOAD postgres;

                DETACH DATABASE IF EXISTS my_db;
                ATTACH DATABASE '{database_url.value}' AS my_db  (TYPE postgres, READ_ONLY);
            """
        )
    return (my_db,)


@app.cell
def _(duckdb):
    duckdb.sql("SHOW DATABASES").show()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Tables""")
    return


@app.cell
def _(mo):
    _df = mo.sql(
        f"""
        SHOW ALL TABLES;
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Other meta table functions""")
    return


@app.cell
def _():
    FUNCTIONS = [
        "duckdb_columns()",  # columns
        "duckdb_constraints()",  # constraints
        "duckdb_databases()",  # lists the databases that are accessible from within the current DuckDB process
        "duckdb_dependencies()",  # dependencies between objects
        "duckdb_extensions()",  # extensions
        "duckdb_functions()",  # functions
        "duckdb_indexes()",  # secondary indexes
        "duckdb_keywords()",  # DuckDB's keywords and reserved words
        "duckdb_optimizers()",  # the available optimization rules in the DuckDB instance
        "duckdb_schemas()",  # schemas
        "duckdb_sequences()",  # sequences
        "duckdb_settings()",  # settings
        "duckdb_tables()",  # base tables
        "duckdb_types()",  # data types
        "duckdb_views()",  # views
        "duckdb_temporary_files()",  # the temporary files DuckDB has written to disk, to offload data from memory
    ]
    return (FUNCTIONS,)


@app.cell
def _(FUNCTIONS, mo):
    function = mo.ui.dropdown(
        label="Dropdown",
        options=FUNCTIONS,
        value=FUNCTIONS[0],
    )
    function
    return (function,)


@app.cell
def _(function, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM {function.value} WHERE database_name == 'my_db'
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Interact with your tables""")
    return


@app.cell
def _(duckdb, mo):
    tables = duckdb.execute(
        """
    SELECT table_name FROM duckdb_tables() WHERE internal = False;
    """
    ).df()
    table_names = list(tables["table_name"])
    mo.accordion({f"Found {len(table_names)} tables": table_names})
    return (table_names,)


@app.cell
def _(mo, table_names):
    mo.stop(not table_names)
    table_select = mo.ui.dropdown(
        label="Table",
        options=table_names,
    )
    limit = mo.ui.slider(
        label="Limit",
        start=100,
        stop=10_000,
        step=10,
        debounce=True,
        show_value=True,
    )
    mo.hstack([table_select, limit]).left()
    return limit, table_select


@app.cell
def _(mo, table_select):
    mo.stop(not table_select.value)
    table_select_value = table_select.value
    return (table_select_value,)


@app.cell
def _(limit, mo, my_db, null, table_select_value):
    selected_table = mo.sql(
        f"""
        select * from my_db.{table_select_value} LIMIT {limit.value};
        """
    )
    return (selected_table,)


@app.cell
def _(mo, selected_table):
    mo.ui.data_explorer(selected_table)
    return


if __name__ == "__main__":
    app.run()
