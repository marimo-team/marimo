# Using SQL

marimo lets you can mix and match **Python and SQL**: Use SQL to query
Python dataframes (or databases like SQLite and Postgres), and get
the query result back as a Python dataframe.

To create a SQL cell, you first need to install additional dependencies,
including [duckdb](https://duckdb.org/):

/// tab | install with pip

```bash
pip install "marimo[sql]"
```

///

/// tab | install with uv

```bash
uv add "marimo[sql]"
```

///

/// tab | install with conda

```bash
conda install -c conda-forge marimo duckdb polars
```

///

!!! example "Examples"

    For example notebooks, check out
    [`examples/sql/` on GitHub](https://github.com/marimo-team/marimo/tree/main/examples/sql/).

## Example

In this example notebook, we have a Pandas dataframe and a SQL cell
that queries it. Notice that the query result is returned as a Python
dataframe and usable in subsequent cells.

<iframe src="https://marimo.app/l/38dxkd?embed=true" class="demo xlarge" height="800px" frameBorder="0"> </iframe>

## Creating SQL cells

You can create SQL cells in one of three ways:

1. **Right-click** an "add cell" button ("+" icon) next to a cell and choose "SQL cell"
2. Convert a empty cell to SQL via the cell
   context menu
3. Click the SQL button that appears at the bottom of the notebook

<div align="center">
  <figure>
    <img src="/_static/docs-sql-cell.png"/>
    <figcaption>Add SQL Cell</figcaption>
  </figure>
</div>

This creates a "**SQL**" cell for you, which is syntactic sugar for Python code.
The underlying code looks like:

```python
output_df = mo.sql(f"SELECT * FROM my_table LIMIT {max_rows.value}")
```

Notice that we have an **`output_df`** variable in the cell. This contains
the query result, and is a Polars DataFrame (if you have `polars` installed) or
a Pandas DataFrame (if you don't). One of them must be installed in order to
interact with the query result.

The SQL statement itself is an f-string, letting you
interpolate Python values into the query with `{}`. In particular, this means
your SQL queries can depend on the values of UI elements or other Python values,
and they are fit into marimo's reactive dataflow graph.

## SQL Output Types

marimo supports different output types for SQL queries, which is particularly useful when working with large datasets. You can configure this in your application configuration in the top right of the marimo editor.

The available options are:

- `native`: Uses DuckDB's native lazy relation (recommended for best performance)
- `lazy-polars`: Returns a lazy Polars DataFrame
- `pandas`: Returns a Pandas DataFrame
- `polars`: Returns an eager Polars DataFrame
- `auto`: Automatically chooses based on installed packages (first tries `polars` then `pandas`)

For best performance with large datasets, we recommend using `native` to avoid loading the entire result set into memory and to more easily chain SQL cells together. By default, only the first 10 rows are displayed in the UI to prevent memory issues.

??? note "Set a default"

  The default output type is currently `auto`, but we recommend explicitly setting the output type to `native` for best performance with large datasets or `polars` if you need to work with the results in Python code. You can configure this in your application settings.

## Reference a local dataframe

You can reference a local dataframe in your SQL cell by using the name of the
Python variable that holds the dataframe. If you have a database connection
with a table of the same name, the database table will be used instead.

<div align="center">
  <figure>
    <img src="/_static/docs-sql-df.png"/>
    <figcaption>Reference a dataframe</figcaption>
  </figure>
</div>

Since the output dataframe variable (`_df`) has an underscore, making it private, it is not referenceable from other cells.

## Reference the output of a SQL cell

Defining a non-private (non-underscored) output variable in the SQL cell allows you to reference the resulting dataframe in other Python and SQL cells.

<div align="center">
  <figure>
    <img src="/_static/docs-sql-http.png"/>
    <figcaption>Reference the SQL result</figcaption>
  </figure>
</div>

## Querying files, databases, and APIs

In the above example, you may have noticed we queried an HTTP endpoint instead
of a local dataframe. We are not only limited to querying local dataframes; we
can also query files, databases such as Postgres and SQLite, and APIs:

```sql
-- or
SELECT * FROM 's3://my-bucket/file.parquet';
-- or
SELECT * FROM read_csv('path/to/example.csv');
-- or
SELECT * FROM read_parquet('path/to/example.parquet');
```

For a full list you can check out the [duckdb extensions](https://duckdb.org/docs/extensions/overview).
You can also check out our [examples on GitHub](https://github.com/marimo-team/marimo/tree/main/examples/sql).

## Escaping SQL brackets

Our "SQL" cells are really just Python under the hood to keep notebooks as pure Python scripts. By default, we use `f-strings` for SQL strings, which allows for parameterized SQL like which allows for parameterized SQL like `SELECT * from table where value < {min}`.

To escape real `{`/`}` that you don't want parameterized, use double `{{...}}`:

```sql
SELECT unnest([{{'a': 42, 'b': 84}}, {{'a': 100, 'b': NULL}}]);
```

## Connecting to a custom database

There are two ways to connect to a database in marimo:

### 1. Using the UI

Click the "Add Database Connection" button in your notebook to connect to PostgreSQL, MySQL, SQLite, DuckDB, Snowflake, or BigQuery databases. The UI will guide you through entering your connection details securely. Environment variables picked up from your [`dotenv`](../configuration/runtime_configuration.md#environment-variables) can be used to fill out the database configuration fields.

<div align="center">
  <figure>
    <img width="700" src="/_static/docs-sql-choose-db.png"/>
    <figcaption>Add a database connection through the UI</figcaption>
  </figure>
</div>

If you'd like to connect to a database that isn't supported by the UI, you can use the code method below, or submit a [feature request](https://github.com/marimo-team/marimo/issues/new?title=New%20database%20connection:&labels=enhancement&template=feature_request.yaml).

### 2. Using Code

You can bring your own database via a **connection engine** created with a library like [SQLAlchemy](https://docs.sqlalchemy.org/en/20/core/connections.html#basic-usage), [SQLModel](https://sqlmodel.tiangolo.com/tutorial/create-db-and-table/?h=create+engine#create-the-engine), or a [custom DuckDB connection](https://duckdb.org/docs/api/python/overview.html#connection-options). By default, marimo uses the [In-Memory duckdb connection](https://duckdb.org/docs/connect/overview.html#in-memory-database).

Define the engine as a Python variable in a cell:

```python
import sqlalchemy
import sqlmodel
import duckdb

# Create an in-memory SQLite database with SQLAlchemy
sqlite_engine = sqlachemy.create_engine("sqlite:///:memory:")
# Create a Postgres database with SQLModel
postgres_engine = sqlmodel.create_engine("postgresql://username:password@server:port/database")
# Create a DuckDB connection
duckdb_conn = duckdb.connect("file.db")
```

### Querying a custom database

marimo will auto-discover the engine and let you select it in the SQL cell's connection dropdown.

<div align="center">
  <figure>
    <img width="750" src="/_static/docs-sql-engine-dropdown.png"/>
    <figcaption>Choose a custom database connection</figcaption>
  </figure>
</div>

### ClickHouse Support

marimo supports ClickHouse via [ClickHouse Connect](https://clickhouse.com/docs/integrations/python#introduction) for remote connections or [chDB](https://clickhouse.com/docs/chdb) for embedded connections.

/// tab | clickhouse_connect

Refer to [the official docs](https://clickhouse.com/docs/integrations/python#gather-your-connection-details) for more configuration options.

```python
import clickhouse_connect

engine = clickhouse_connect.get_client(host="localhost", port=8123, username="default", password="password")
```

///

/// tab | chDB

!!! warning

    chDB is still new. You may experience issues with your queries. We recommend only using one connection at a time.
    Refer to [chDB docs](https://github.com/orgs/chdb-io/discussions/295) for more information.

```python
import chdb

connection = chdb.connect(":memory:")

# Supported formats with examples:
":memory:"                                   # In-memory database
"test.db"                                    # Relative path
"file:test.db"                               # Explicit file protocol
"/path/to/test.db"                           # Absolute path
"file:/path/to/test.db"                      # Absolute path with protocol
"file:test.db?param1=value1&param2=value2"   # With query parameters
"file::memory:?verbose&log-level=test"       # In-memory with parameters
"///path/to/test.db?param1=value1"           # Triple slash absolute path
```

///

## Database, schema, and table auto-discovery

marimo will automatically discover the database connection and display the database, schemas, tables, and columns in the Data Sources panel. This panels lets you quickly navigate your database schema and reference tables and columns to pull in your SQL queries.

<div align="center">
  <figure>
    <img src="/_static/docs-sql-datasources-panel.png"/>
    <figcaption>Data Sources panel</figcaption>
  </figure>
</div>

???+ note

    By default, marimo auto-discovers databases and schemas, but not tables and columns (to avoid performance issues with large databases). You can configure this behavior in your `pyproject.toml` file. Options are `true`, `false`, or `"auto"`. `"auto"` will determine whether to auto-discover based on the type of database (e.g. when the value is `"auto"`, Snowflake and BigQuery will not auto-discover tables and columns while SQLite, Postgres, and MySQL will):

    ```toml title="pyproject.toml"
    [tool.marimo.datasources]
    auto_discover_schemas = true   # Default: true
    auto_discover_tables = "auto"   # Default: "auto"
    auto_discover_columns = "auto"  # Default: false
    ```

## Catalogs

marimo supports connecting to Iceberg catalogs. You can click the "plus" button in the Datasources panel or manually create a [PyIceberg](https://py.iceberg.apache.org/) `Catalog` connection. PyIceberg supports a variety of catalog implementations including REST, SQL, Glue, DynamoDB, and more.

```python
from pyiceberg.catalog.rest import RestCatalog

catalog = RestCatalog(
    name="catalog",
    warehouse="1234567890",
    uri="https://my-catalog.com",
    token="my-token",
)
```

Catalogs will appear in the Datasources panel, but they cannot be used as an engine in SQL cells. However, you can still load the table into one cell and use it in subsequent Python or SQL cells.

```python
df = catalog.load_table(("my-namespace", "my-table")).to_polars()
```

```sql
SUMMARIZE df;
```

## Interactive tutorial

For an interactive tutorial, run

```bash
marimo tutorial sql
```

at your command-line.

## Examples

Check out our [examples on GitHub](https://github.com/marimo-team/marimo/tree/main/examples/sql).
