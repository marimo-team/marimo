# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.7.13"
app = marimo.App()


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        # Hello, SQL!

        _Let's dive into the world of SQL where we don't just address tables, we also join them!_
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        With marimo, you can mix-and-match both **Python and SQL**. To create a
        SQL cell, you first need to install some additional dependencies,
        including [duckdb](https://duckdb.org/). Obtain these dependencies with

        ```bash
        pip install marimo[sql]
        ```
        """
    )
    return


@app.cell(hide_code=True)
def __():
    has_duckdb_installed = False
    try:
        import duckdb

        has_duckdb_installed = True
    except ImportError:
        pass

    has_polars_installed = False
    try:
        import polars

        has_polars_installed = True
    except ImportError:
        pass

    has_pandas_installed = False
    try:
        import pandas

        has_pandas_installed = True
    except ImportError:
        pass
    return (
        duckdb,
        has_duckdb_installed,
        has_pandas_installed,
        has_polars_installed,
        pandas,
        polars,
    )


@app.cell(hide_code=True)
def __(has_duckdb_installed, mo):
    if has_duckdb_installed:
        mo.output.replace(
            mo.md(
                """
        !!! Tip "Installed"
            If you see this, DuckDB is already installed.
        """
            )
        )
    else:
        mo.output.replace(
            mo.md(
                """
        !!! Warning "Not Installed"
            If you see this, DuckDB is not installed.
        """
            )
        )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        Once the required dependencies are installed, you can create SQL cells
        by either right clicking the **Add Cell** buttons on the left of a
        cell, or click the **Add SQL Cell** at the bottom of the page.

        marimo is still just Python, even when using SQL. Here is an example of
        how marimo embeds SQL in Python in its file format:

        ```python
        output_df = mo.sql(f"SELECT * FROM my_table LIMIT {max_rows.value}")
        ```

        Notice that we have an **`output_df`** variable in the cell. This is a
        resulting Polars DataFrame (if you have `polars` installed) or a Pandas
        DataFrame (if you don't). One of them must be installed in order to
        interact with the SQL result.

        The SQL statement itself is an formatted string (f-string), so this
        means they can contain any valid Python code, such as the values of UI
        elements. This means your SQL statement and results can be reactive! 🚀
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("## Querying dataframes with SQL")
    return


@app.cell
def __(mo):
    mo.md(r"""Let's take a look at a SQL cell. The next cell generates a dataframe called `df`.""")
    return


@app.cell(hide_code=True)
def __(has_polars_installed):
    _SIZE = 1000


    def _create_token_data(n_items=100):
        import random
        import string

        def generate_random_string(length):
            letters = string.ascii_lowercase
            result_str = "".join(random.choice(letters) for i in range(length))
            return result_str

        def generate_random_numbers(mean, std_dev, num_samples):
            return [int(random.gauss(mean, std_dev)) for _ in range(num_samples)]

        random_numbers = generate_random_numbers(50, 15, n_items)
        random_strings = sorted(
            list(set([generate_random_string(3) for _ in range(n_items)]))
        )

        return {
            "token": random_strings,
            "count": random_numbers[: len(random_strings)],
        }


    _data = _create_token_data(_SIZE)

    # Try polars
    if has_polars_installed:
        import polars as pl

        df = pl.DataFrame(_data)
    # Fallback to pandas (maybe trying to install it)
    else:
        import pandas as pd

        df = pd.DataFrame(_data)
    return df, pd, pl


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""Next, we create a SQL query, refercing the Python dataframe `df` directly.""")
    return


@app.cell
def __(df, mo):
    _df = mo.sql(
        f"""
        -- This SQL cell is special since we can reference existing dataframes in the global scope as a table in the SQL query. For example, we can reference the `df` dataframe in the global scope, which was defined in another cell using Python.

        SELECT * FROM df;

        -- By default, the output variable starts with an underscore (`_df`), making it private to this cell. To access the query result in another cell, change the name of the output variable.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""## From Python to SQL and back""")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""You can create SQL statements that depend on Python values, such as UI elements:""")
    return


@app.cell(hide_code=True)
def __(mo, string):
    token_prefix = mo.ui.dropdown(
        list(string.ascii_lowercase), label="token prefix", value="a"
    )
    token_prefix
    return token_prefix,


@app.cell
def __(df, mo, token_prefix):
    result = mo.sql(
        f"""
        -- Change the dropdown to see the SQL query filter itself!
        --
        -- Here we use a duckdb function called `starts_with`:
        SELECT * FROM df WHERE starts_with(token, '{token_prefix.value}')

        -- Notice that we named the output variable `result`
        """
    )
    return result,


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        Since we named the output variable above **`result`**,
        we can use it back in Python.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    charting_library = mo.ui.radio(["matplotlib", "altair", "plotly"])

    mo.md(
        f"""
        Let's chart the result with a library of your choice:

        {charting_library}
        """
    )
    return charting_library,


@app.cell(hide_code=True)
def __(charting_library, mo, render_chart, token_prefix):
    _header = mo.md(
        f"""
        We can re-use the dropdown from above: {token_prefix}

        Now we have a histogram visualizing the token count distribution of tokens starting
        with {token_prefix.value}, powered by your SQL query and UI element.
        """
    )

    render_chart(
        charting_library.value, _header
    ) if charting_library.value else None
    return


@app.cell(hide_code=True)
def __(mo, result, token_prefix):
    def render_chart(charting_library, header):
        return mo.vstack(
            [header, render_charting_library(charting_library)]
        ).center()


    def render_charting_library(charting_library):
        if charting_library == "matplotlib":
            return render_matplotlib()
        if charting_library == "altair":
            return render_altair()
        if charting_library == "plotly":
            return render_plotly()


    def render_matplotlib():
        import matplotlib.pyplot as plt

        plt.hist(result["count"], label=token_prefix.value)
        plt.xlabel("token count")
        plt.legend()
        plt.tight_layout()
        return plt.gcf()


    def render_altair():
        import altair as alt

        chart = (
            alt.Chart(result)
            .mark_bar()
            .encode(x=alt.X("count", bin=True), y=alt.Y("count()"))
        )
        return mo.ui.altair_chart(chart, chart_selection=False)


    def render_plotly():
        import plotly.graph_objects as go

        return go.Figure(data=[go.Histogram(x=result["count"])])
    return (
        render_altair,
        render_chart,
        render_charting_library,
        render_matplotlib,
        render_plotly,
    )


@app.cell
def __(mo):
    mo.md(r"""## CSVs, Parquet, Postgres, and more ...""")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        We're not limited to querying dataframes. We can also query an **HTTP URL, S3 path, or a file path to a local csv or parquet file**.

        ```sql
        -- or
        SELECT * FROM 's3://my-bucket/file.parquet';
        -- or
        SELECT * FROM read_csv('path/to/example.csv');
        -- or
        SELECT * FROM read_parquet('path/to/example.parquet');
        ```

        With a bit of boilerplate, you can even read and write to **Postgres**, and join Postgres tables with dataframes in the same query. For a full list of supported data sources, check out the [duckdb extensions](https://duckdb.org/docs/extensions/overview) and our [example notebook on duckdb connections](https://github.com/marimo-team/marimo/blob/main/examples/sql/duckdb_connections.**py**).

        For this example, we will query an HTTP endpoint of a csv.
        """
    )
    return


@app.cell
def __(cars, mo):
    cars = mo.sql(
        f"""
        -- Download a CSV and create an in-memory table; this is optional.
        CREATE OR replace TABLE cars as
        FROM 'https://datasets.marimo.app/cars.csv';

        -- Query the table
        SELECT * from cars;
        """
    )
    return cars,


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        !!! Tip "Data sources panel"
            Click the database "barrel" icon in the left toolbar to see all dataframes and in-
            memory tables that you're notebook has access to.
        """
    )
    return


@app.cell(hide_code=True)
def __(cars, mo):
    cylinders_dropdown = mo.ui.range_slider.from_series(
        cars["Cylinders"], debounce=True, show_value=True
    )
    origin_dropdown = mo.ui.dropdown.from_series(cars["Origin"], value="Asia")
    mo.hstack([cylinders_dropdown, origin_dropdown]).left()
    return cylinders_dropdown, origin_dropdown


@app.cell
def __(cars, cylinders_dropdown, mo, origin_dropdown):
    filtered_cars = mo.sql(
        f"""
        SELECT * FROM cars
        WHERE
            Cylinders >= {cylinders_dropdown.value[0]}
            AND
            Cylinders <= {cylinders_dropdown.value[1]}
            AND
            ORIGIN = '{origin_dropdown.value}'
        """
    )
    return filtered_cars,


@app.cell(hide_code=True)
def __(filtered_cars, mo):
    mo.hstack(
        [
            mo.stat(label="Total cars", value=str(len(filtered_cars))),
            mo.stat(
                label="Average MPG Highway",
                value=f"{filtered_cars['MPG_Highway'].mean() or 0:.1f}",
            ),
            mo.stat(
                label="Average MPG City",
                value=f"{filtered_cars['MPG_City'].mean() or 0:.1f}",
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def __():
    import marimo as mo
    import random
    return mo, random


@app.cell(hide_code=True)
def __():
    import string
    return string,


if __name__ == "__main__":
    app.run()
