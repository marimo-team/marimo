# MotherDuck

MotherDuck is a cloud-based data warehouse that combines the power of DuckDB with the scalability of the cloud. This guide will help you integrate MotherDuck with marimo.

## 1. Connecting to MotherDuck

To use MotherDuck as a data source, you'll need to install the `marimo[sql]` Python package.

````bash
::::{tab-set}
:::{tab-item} install with pip

```bash
pip install marimo[sql]
````

:::
:::{tab-item} install with uv

```bash
uv pip install marimo[sql]
```

:::
:::{tab-item} install with conda

```bash
conda install -c conda-forge marimo[sql]
```

:::
::::

To connect to MotherDuck, import `duckdb` and `ATTACH` your MotherDuck database.

```python
import duckdb

# Connect to MotherDuck
duckdb.sql("ATTACH 'md:your_motherduck_database_name' AS sample_data")
```

You will be prompted to authenticate with MotherDuck when you run the above cell. This will open a browser window where you can log in and authorize marimo to access your MotherDuck database. In order to avoid being prompted each time you open a notebook, you can set the `motherduck_token` environment variable:

```bash
export motherduck_token="your_motherduck_token_here"
marimo edit
```

You can obtain this token from your MotherDuck account settings.

Once you've authenticated, your MotherDuck tables get automatically discovered and you can browse them from the Datasources Panel.

<div align="center">
  <figure>
    <img src="/_static/motherduck/motherduck_db_discovery.png"/>
    <figcaption>Attach to a MotherDuck database</figcaption>
  </figure>
</div>

## 2. Querying Your Tables

Once connected, you can query your MotherDuck tables using SQL. Here's an example of how to query a table and display the results using marimo:

<div align="center">
  <figure>
    <img src="/_static/motherduck/motherduck_sql.png"/>
    <figcaption>Query a MotherDuck table</figcaption>
  </figure>
</div>

marimo's reactive execution model extends into SQL queries, so changes to your SQL will automatically trigger downstream computations for dependent cells.

<video controls width="100%" height="100%" align="center" src="/_static/motherduck/motherduck_reactivity.mp4"> </video>

## 3. Mixing SQL and Python

MotherDuck allows you to seamlessly mix SQL queries with Python code, enabling powerful data manipulation and analysis. Here's an example:

<div align="center">
  <figure>
    <img src="/_static/motherduck/motherduck_python_and_sql.png"/>
    <figcaption>Mixing SQL and Python</figcaption>
  </figure>
</div>

This example demonstrates how you can use SQL to query your data, then use Python and marimo to further analyze and visualize the results.

## Example

For a full example of using MotherDuck with marimo, check out our [MotherDuck example notebook](https://github.com/marimo-team/marimo/blob/main/examples/sql/connect_to_motherduck.py).

```bash
marimo edit https://github.com/marimo-team/marimo/blob/main/examples/sql/connect_to_motherduck.py
```
