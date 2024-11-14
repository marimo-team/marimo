# SQL

marimo lets you can mix and match **Python and SQL**: Use SQL to query
Python dataframes (or databases like SQLite and Postgres), and get
the query result back as a Python dataframe.

To create a SQL cell, you first need to install additional dependencies,
including [duckdb](https://duckdb.org/):

::::{tab-set}
:::{tab-item} install with pip

```bash
pip install "marimo[sql]"
```

:::
:::{tab-item} install with uv

```bash
uv pip install "marimo[sql]"
```

:::
:::{tab-item} install with conda

```bash
conda install -c conda-forge marimo duckdb polars
```

:::
::::

```{admonition} Examples
:class: tip

For example notebooks, check out
[`examples/sql/` on GitHub](https://github.com/marimo-team/marimo/tree/main/examples/sql/).
```

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

## Interactive tutorial

For an interactive tutorial, run

```bash
marimo tutorial sql
```

at your command-line.

## Examples

Check out our [examples on GitHub](https://github.com/marimo-team/marimo/tree/main/examples/sql).
