---
description: "API reference for mo.sql — execute SQL queries against DuckDB or a custom engine in marimo notebooks."
---

# SQL

Execute SQL with `mo.sql`. By default this runs against DuckDB so dataframes in the global namespace can be queried directly. Pass a custom engine to target other databases.

!!! note

    Autodoc via `::: marimo.sql` cannot resolve the public re-export today: the
    implementation lives under the private package `marimo._sql`, which mkdocstrings
    filters out (`!^_`). The signature and docs below match
    `marimo._sql.sql.sql` as exposed on `marimo.sql` / `mo.sql`.

## `mo.sql`

```python
def sql(
    query: str,
    *,
    output: bool = True,
    engine: DBAPIConnection | None = None,
) -> Any
```

Execute a SQL query.

By default, this uses duckdb to execute the query. Any dataframes in the global
namespace can be used inside the query.

You can also pass a custom engine to execute queries against other databases.
The custom engine can be a DB-API 2.0 compatible connection (PEP 249), including
DB-API wrappers provided by ADBC drivers.

The result of the query is displayed in the UI if `output` is `True`.

**Args**

- `query`: The SQL query to execute.
- `output`: Whether to display the result in the UI. Defaults to `True`.
- `engine`: Optional SQL engine to use. Can be a SQLAlchemy, DuckDB, Clickhouse,
  Redshift, Ibis, or DB-API 2.0 compatible connection (including ADBC drivers).
  If `None`, uses DuckDB.

**Returns**

- The result of the query.

See also the [SQL guide](../guides/working_with_data/sql.md).
