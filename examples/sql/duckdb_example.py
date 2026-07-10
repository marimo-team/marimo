# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.5.0",
#     "polars[pyarrow]==1.27.1",
#     "marimo[sql]",
#     "duckdb==1.2.2",
#     "sqlglot==26.13.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium", sql_output="polars")


@app.cell
def _():
    import marimo as mo
    import altair as alt

    return alt, mo


@app.cell
def _(mo):
    digits = mo.ui.slider(label="Digits", start=100, stop=10000, step=200)
    digits
    return (digits,)


@app.cell
def _(digits, mo):
    result = mo.sql(
        f"""
        CREATE TABLE random_data AS
        SELECT i AS id, RANDOM() AS random_value,
        FROM range({digits.value}) AS t(i);

        SELECT * FROM random_data;
        """
    )
    return (result,)


@app.cell
def _(alt, result):
    # Plot the data using polars and altair
    result.plot.bar(x=alt.X("random_value").bin(), y="count()")
    return


if __name__ == "__main__":
    app.run()
