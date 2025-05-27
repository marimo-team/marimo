# MotherDuck

[MotherDuck](https://motherduck.com/) is a cloud-based data warehouse that combines the power of DuckDB with the scalability of the cloud. This guide will help you integrate MotherDuck with marimo.

## 1. Connecting to MotherDuck

To use MotherDuck as a data source, you'll need to install the `marimo[sql]` Python package.

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

To connect to MotherDuck, import `duckdb` and `ATTACH` your MotherDuck database.

## Using MotherDuck

### 1. Connecting and Database Discovery

/// tab | SQL

```sql
ATTACH IF NOT EXISTS 'md:my_db'
```

///

/// tab | Python

```python
import duckdb
# Connect to MotherDuck
duckdb.sql("ATTACH IF NOT EXISTS 'md:my_db'")
```

///

You will be prompted to authenticate with MotherDuck when you run the above cell. This will open a browser window where you can log in and authorize your marimo notebook to access your MotherDuck database. In order to avoid being prompted each time you open a notebook, you can set the `motherduck_token` environment variable:

```bash
export motherduck_token="your_token"
marimo edit
```

Once connected, your MotherDuck tables are automatically discovered in the Datasources Panel:

<div align="center">
  <figure>
    <img src="/_static/motherduck/motherduck_db_discovery.png"/>
    <figcaption>Browse your MotherDuck databases</figcaption>
  </figure>
</div>

### 2. Writing SQL Queries

You can query your MotherDuck tables using SQL cells in marimo. Here's an example of how to query a table and display the results using marimo:

<div align="center">
  <figure>
    <img src="/_static/motherduck/motherduck_sql.png"/>
    <figcaption>Query a MotherDuck table</figcaption>
  </figure>
</div>

marimo's reactive execution model extends into SQL queries, so changes to your SQL will automatically trigger downstream computations for dependent cells (or optionally mark cells as stale for expensive computations).

<video controls width="100%" height="100%" align="center" src="/_static/motherduck/motherduck_reactivity.mp4"> </video>

### 3. Mixing SQL and Python

MotherDuck allows you to seamlessly mix SQL queries with Python code, enabling powerful data manipulation and analysis. Here's an example:

<div align="center">
  <figure>
    <img src="/_static/motherduck/motherduck_python_and_sql.png"/>
    <figcaption>Mixing SQL and Python</figcaption>
  </figure>
</div>

This example demonstrates how you can use SQL to query your data, then use Python and marimo to further analyze and visualize the results.

## Example Notebook

For a full example of using MotherDuck with marimo, check out our [MotherDuck example notebook](https://github.com/marimo-team/marimo/blob/main/examples/sql/connect_to_motherduck.py).

```bash
marimo edit https://github.com/marimo-team/marimo/blob/main/examples/sql/connect_to_motherduck.py
```
