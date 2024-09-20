import marimo

__generated_with = "0.8.17"
app = marimo.App()


@app.cell(hide_code=True)
def __():
    import marimo as mo
    import os
    import duckdb
    from pathlib import Path
    import altair as alt
    return Path, alt, duckdb, mo, os


@app.cell
def __(Path, __file__, mo, os):
    dirname = Path(os.path.dirname(__file__))
    # Use mo.filewatch to watch the SQL file
    sql_content = mo.filewatch(dirname / "query.sql")
    return dirname, sql_content


@app.cell
def __():
    # Load the cars dataset
    from vega_datasets import data
    cars = data.cars()
    return cars, data


@app.cell
def __(chart, duckdb, sql_content):
    query = sql_content()
    result = duckdb.sql(query)
    chart(result.df())
    return query, result


@app.cell
def __(mo, query):
    mo.md(f"""```sql
    SQL: query
    {query}
    ```""")
    return


@app.cell
def __(alt):
    def chart(data):
        return alt.Chart(data).mark_bar().encode(
        x=alt.X('Miles_per_Gallon', bin=alt.Bin(maxbins=30)),
        y='count()'
    ).properties(width="container")
    return (chart,)


if __name__ == "__main__":
    app.run()
