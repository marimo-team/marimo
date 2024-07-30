# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.7.12"
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
        With marimo, you can mix-and-match both **Python and SQL**. To create a SQL cell, you first need to install our SQL query engine of choice: [duckdb](https://duckdb.org/).

        ```bash
        pip install duckdb
        ```

        Or if you `import duckdb` in any SQL cell, marimo will automatically install it for you.
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
            If you see this, it means DuckDB is already installed.
        """
            )
        )
    else:
        mo.output.replace(
            mo.md(
                """
        !!! Warning "Not Installed"
            If you see this, it means DuckDB is not installed.
        """
            )
        )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        Once installed, you can either right-click the **Add Cell** buttons on the left, or click the **Add SQL Cell** at the bottom of the page. This creates a '**SQL**' cell for you, while in reality this is actually Python code.

        For example, since we store marimo files as pure Python files, the translated code looks like:

        ```python
        output_df = mo.sql(f"SELECT * FROM my_table LIMIT {max_rows.value}")
        ```

        Notice that we have an **`output_df`** variable in the cell. This is a resulting Polars DataFrame (if you have `polars` installed) or a Pandas DataFrame (if you don't). One of them must be installed in order to interact with the SQL result.

        The SQL statement itself is an formatted string (f-string), so this means they can contain any valid Python code, such as the values of UI elements. This means your SQL statement and results can be reactive! 🚀

        Let's take a look at a SQL cell. First we will create a dataframe
        """
    )
    return


@app.cell(hide_code=True)
def __(has_polars_installed, random):
    _SIZE = 20
    # Try polars
    if has_polars_installed:
        import polars as pl

        df = pl.DataFrame(
            {
                "a": [random.randint(0, 1000) for _ in range(_SIZE)],
                "b": [random.randint(0, 1000) for _ in range(_SIZE)],
            }
        )
    # Fallback to pandas (maybe trying to install it)
    else:
        import pandas as pd

        df = pd.DataFrame(
            {
                "a": [random.randint(0, 1000) for _ in range(_SIZE)],
                "b": [random.randint(0, 1000) for _ in range(_SIZE)],
            }
        )
    return df, pd, pl


@app.cell
def __(df, mo):
    _df = mo.sql(
        f"""
        -- This SQL cell is special since we can reference existing dataframes in the global scope as a table in the SQL query. For example, we can reference the `df` dataframe in the global scope, which was defined in another cell using Python.

        SELECT * FROM df;

        -- Since the output dataframe variable (`_df`) has an underscore, making it private, it is not referenceable from other cells.
        """
    )
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""Let's look at another SQL statement, but this time with a UI element""")
    return


@app.cell(hide_code=True)
def __(df, mo):
    max_b_value = mo.ui.slider(
        start=df["b"].min(),
        stop=df["b"].max(),
        value=df["b"].max(),
        label="Max $b$",
        debounce=True,
    )
    max_b_value
    return max_b_value,


@app.cell
def __(df, max_b_value, mo):
    result = mo.sql(
        f"""
        -- Move the slider's value down in order to see the SQL query filter itself
        SELECT * FROM df
        WHERE b < {max_b_value.value}
        """
    )
    return result,


@app.cell
def __(mo):
    mo.md(
        r"""
        Since we named the output dataframe above **`result`**,
        we can reference this back in Python
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
def __(charting_library, max_b_value, mo, render_chart):
    _header = mo.md(
        f"""
        We can re-use the slider from above: {max_b_value}

        Now we have a plot powered by your previous SQL query and your UI elements.
        """
    )

    render_chart(
        charting_library.value, _header
    ) if charting_library.value else None
    return


@app.cell(hide_code=True)
def __(mo, result):
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

        plt.scatter(result["a"], result["b"])
        return plt.gcf()


    def render_altair():
        import altair as alt

        chart = alt.Chart(result).mark_point().encode(x="a", y="b")
        return mo.ui.altair_chart(chart)


    def render_plotly():
        import plotly.express as px

        fig = px.scatter(result, x="a", y="b")
        return mo.ui.plotly(fig)
    return (
        render_altair,
        render_chart,
        render_charting_library,
        render_matplotlib,
        render_plotly,
    )


@app.cell(hide_code=True)
def __(mo):
    mo.md(
        r"""
        We are not only limited to querying dataframes that we have created or pulled in.
        We can additionally query by an **HTTP URL, S3 path, or a file path to a local csv or parquet file**.

        ```sql
        -- or
        SELECT * FROM 's3://my-bucket/file.parquet';
        -- or
        SELECT * FROM read_csv('path/to/example.csv');
        -- or
        SELECT * FROM read_parquet('path/to/example.parquet');
        ```

        For a full list you can check out the [duckdb extensions](https://duckdb.org/docs/extensions/overview).

        For this example, we will query an HTTP endpoint of a csv.
        """
    )
    return


@app.cell
def __(cars, mo):
    cars = mo.sql(
        f"""
        -- Download a CSV and create an in-memory table
        CREATE OR replace TABLE cars as
        FROM 'https://datasets.marimo.app/cars.csv';
        SELECT * from cars;
        """
    )
    return cars,


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


if __name__ == "__main__":
    app.run()
