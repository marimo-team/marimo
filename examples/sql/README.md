# SQL 🛢️

These examples show how to use marimo's built-in support for SQL, which
is powered by [duckdb](https://duckdb.org/), a fast in-process
analytical database.

- `querying_dataframes.py` shows hows to query Pandas or Polars dataframes
- `paremetrizing_sql_queries.py` shows hows to parametrize queries with Python values
- `read_csv.py` shows hows to read CSV data into duckdb
- `read_json.py` shows hows to read JSON data into duckdb
- `read_parquet.py` shows hows to read parquet data into duckdb
- `connect_to_sqlite.py` shows hows to connect to a SQLite database
- `connect_to_postgres.py` shows hows to connect to a PostgreSQL database
- `connect_to_motherduck.py` shows hows to connect to [motherduck](https://motherduck.com)
- [`misc/`](misc/) contains illustrative examples

> [!TIP]
> For a broad overview of using SQL in marimo, run `marimo tutorial sql` at the
> command-line.

Consult the [duckdb documentation](https://duckdb.org/docs/index) for a
comprehensive guide on duckdb.

## Running examples

The requirements of each notebook are serialized in them as a top-level
comment. Here are the steps to open an example notebook:

1. [Install marimo](https://docs.marimo.io/getting_started/index.html#installation)
2. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
3. Open an example with `marimo edit --sandbox <notebook.py>`.

> [!TIP]
> The [`--sandbox` flag](https://docs.marimo.io/guides/editor_features/package_management.html) opens the notebook in an isolated virtual environment,
> automatically installing the notebook's dependencies 📦

You can also open notebooks without `uv`, with just `marimo edit <notebook.py>`;
however, you'll need to install the requirements yourself.
