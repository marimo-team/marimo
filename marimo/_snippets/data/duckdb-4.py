# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: Parameterized & Reactive SQL Queries

        This snippet shows how to parameterize SQL queries with Python variables
        in marimo, allowing queries to dynamically reflect changes in Python values.
        """
    )
    return


@app.cell
def _():
    import polars as pl
    # Create a sample DataFrame for reactive filtering
    data = {'id': list(range(1, 21)), 'score': [x * 5 for x in range(1, 21)]}
    df = pl.DataFrame(data)
    return data, df, pl


@app.cell
def _(mo):
    min_score = mo.ui.number(label="Minimum Score", value=50, start=0)
    return (min_score,)


@app.cell
def _(min_score):
    min_score
    return


@app.cell
def _(df, min_score, mo):
    result = mo.sql(
        f"""
        SELECT * FROM df WHERE score >= {min_score.value}
        """
    )
    return (result,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
