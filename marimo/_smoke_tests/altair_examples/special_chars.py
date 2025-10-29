"""Test Altair chart builder with special characters in column names.

This notebook tests the fix for issue #5956, which ensures that special
characters like dots, brackets, and colons in column names are properly
escaped when generating Altair chart code.
"""

import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import polars as pl
    import altair as alt
    return alt, mo, pd, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    # Testing Altair Charts with Special Characters

    This notebook tests column names with special characters:
    - Dots: `.`
    - Brackets: `[`, `]`
    - Colons: `:`

    These characters need to be escaped in Altair field names.
    """
    )
    return


@app.cell
def _(pd):
    # Create a Pandas DataFrame with special column names
    pandas_df = pd.DataFrame(
        {
            "category": ["A", "B", "C", "D", "E"],
            "value.data": [10, 20, 15, 25, 30],
            "info[0]": [5, 10, 8, 12, 15],
            "time:stamp": ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"],
            "complex.name[1]:value": [100, 200, 150, 250, 300],
        }
    )
    pandas_df
    return (pandas_df,)


@app.cell
def _(pandas_df, pl):
    # Create a Polars DataFrame with special column names
    polars_df = pl.DataFrame(pandas_df)
    polars_df
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    Use the data table chart builder to create a chart using `value.data` column.
    The generated Python code should escape the dot: `field='value\\.data'`

    Repeat for all the other columns
    """
    )
    return


@app.cell
def _(mo, pandas_df):
    mo.ui.table(pandas_df, selection=None)
    return


@app.cell
def _(alt, pandas_df):
    chart = (
        alt.Chart(pandas_df)
        .mark_bar()
        .encode(
            x=alt.X(field="category"),
            y=alt.Y(field=r"value\.data"),  # Using escaped field name
        )
    )
    chart
    return


if __name__ == "__main__":
    app.run()
