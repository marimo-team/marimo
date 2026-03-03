# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==1.1.1",
#     "marimo",
#     "numpy==2.0.2",
#     "pandas==2.2.3",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium", layout_file="layouts/slides.slides.json")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    !!! tip "This notebook is best viewed as an app."
        Hit `Cmd/Ctrl+.` or click the "app view" button in the bottom right.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # DuckDB Tricks 🦆

    We use a simple example data set to present a few tricks that are useful when using DuckDB.

    >
    > Turned into slides from <https://duckdb.org/2024/08/19/duckdb-tricks-part-1.html>
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Installation

    ```bash
    uv add duckdb
    ```
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    # Creating the example data set
    """)
    return


@app.cell
def _(duckdb, mo, print_and_run):
    _SQL = """
        CREATE OR REPLACE TABLE example (s STRING, x DOUBLE);
        INSERT INTO example VALUES ('foo', 10/9), ('bar', 50/7), ('qux', 9/4);
        COPY example TO 'example.csv';
    """

    duckdb.sql(_SQL)

    mo.md(
        f"""
        Creating the example data set
        We start by creating a data set that we'll use in the rest of the blog post. To this end, we define a table, populate it with some data and export it to a CSV file.

    {print_and_run(_SQL)}

        Wait a bit, that’s way too verbose! DuckDB’s syntax has several SQL shorthands including the “friendly SQL” clauses. Here, we combine the VALUES clause with the FROM-first syntax, which makes the SELECT clause optional. With these, we can compress the data creation script to ~60% of its original size. The new formulation omits the schema definition and creates the CSV with a single command:

        ```sql
        COPY (FROM VALUES ('foo', 10/9), ('bar', 50/7), ('qux', 9/4) t(s, x))
        TO 'example.csv';
        ```

        Regardless of which script we run, the resulting CSV file will look like this:


        {print_and_run("SELECT * from example")}
        """
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    # Pretty-printing floating-point numbers
    """)
    return


@app.cell
def _(mo, print_and_run):
    mo.md(f"""
    When printing a floating-point number to the output, the fractional parts can be difficult to read and compare. For example, the following query returns three numbers between 1 and 8 but their printed widths are very different due to their fractional parts.

    {print_and_run("SELECT x FROM 'example.csv';")}

    By casting a column to a DECIMAL with a fixed number of digits after the decimal point, we can pretty-print it as follows:

    {print_and_run('''
    SELECT x::DECIMAL(15, 3) AS x
    FROM 'example.csv';
    ''')}

    A typical alternative solution is to use the printf or format functions, e.g.:

    {print_and_run('''
    SELECT printf('%.3f', x)
    FROM 'example.csv';
    ''')}

    However, these approaches require us to specify a formatting string that's easy to forget. What's worse, the statement above returns string values, which makes subsequent operations (e.g., sorting) more difficult. Therefore, unless keeping the full precision of the floating-point numbers is a concern, casting to DECIMAL values should be the preferred solution for most use cases.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    # Copying the schema of a table
    """)
    return


@app.cell
def _(mo, print_and_run):
    mo.md(f"""
    To copy the schema from a table without copying its data, we can use LIMIT 0.

    {print_and_run('''
    CREATE OR REPLACE TABLE example AS
        FROM 'example.csv';
    CREATE OR REPLACE TABLE tbl AS
        FROM example
        LIMIT 0;
    ''')}

    This will result in an empty table with the same schema as the source table:

    {print_and_run('DESCRIBE tbl;')}

    This will return the schema of the table.

    ```sql
    CREATE TABLE example(s VARCHAR, x DOUBLE);
    ```

    After editing the table’s name (e.g., example to tbl), this query can be used to create a new table with the same schema.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    # Shuffling data
    """)
    return


@app.cell
def _(mo):
    rerun = mo.ui.button(label="Run again")
    return (rerun,)


@app.cell
def _(mo, print_and_run, rerun):
    mo.md(f"""
    Sometimes, we need to introduce some entropy into the ordering of the data by shuffling it. To shuffle non-deterministically, we can simply sort on a random value provided the random() function:

    {rerun}

    {print_and_run('''
    FROM 'example.csv' ORDER BY random();
    ''')}

    Shuffling deterministically is a bit more tricky. To achieve this, we can order on the hash, of the rowid pseudocolumn. Note that this column is only available in physical tables, so we first have to load the CSV in a table, then perform the shuffle operation as follows:

    {rerun}

    {print_and_run('''
    CREATE OR REPLACE TABLE example AS FROM 'example.csv';
    FROM example ORDER BY hash(rowid + 42);
    ''')}

    Note that the + 42 is only necessary to nudge the first row from its position – as hash(0) returns 0, the smallest possible value, using it for ordering leaves the first row in its place.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Closing thoughts

    That’s it for today. The tricks shown in this post are available on [duckdbsnippets.com](https://duckdbsnippets.com).
    """)
    return


@app.cell
def _(duckdb, mo):
    # Utils

    def print_and_run(sql: str):
        result = duckdb.sql(sql)
        sql = sql.strip()
        if not result:
            return f"""
        ```sql
        {sql}
        ```
        """
        return f"""
        ```sql
        {sql}
        ```
        {mo.ui.table(result.df(), selection=None, pagination=None, show_column_summaries=False)}
        """

    return (print_and_run,)


@app.cell
def _():
    import marimo as mo
    import duckdb

    return duckdb, mo


if __name__ == "__main__":
    app.run()
