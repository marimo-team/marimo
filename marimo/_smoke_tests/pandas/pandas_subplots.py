# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "matplotlib",
# ]
# ///

import marimo

__generated_with = "0.17.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    # Issue #6893: Pandas Subplots Not Displaying

    This smoke test reproduces the issue where pandas DataFrame box plots
    with `subplots=True` don't render properly in marimo.

    **Expected behavior**: Box plots should display as images

    **Actual behavior**: Only textual representation appears

    The issue occurs because `df.plot.box(subplots=True)` returns a numpy
    ndarray of matplotlib Axes objects, which marimo doesn't currently format.
    """
    )
    return


@app.cell
def _():
    import pandas as pd
    import matplotlib

    # Load NYC taxi data from stable GitHub URL
    taxi_url = (
        "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/taxis.csv"
    )
    df = pd.read_csv(taxi_url)
    df
    return (df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## Test Case 1: Box plot WITHOUT subplots (works correctly)""")
    return


@app.cell
def _(df):
    # This should work - returns a single Axes object
    df[["distance", "total"]].plot.box()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    ## Test Case 2: Box plot WITH subplots (reproduces issue #6893)

    This is the exact scenario from the bug report.
    """
    )
    return


@app.cell
def _(df):
    # This reproduces the issue - returns ndarray of Axes
    df[["distance", "total"]].plot.box(subplots=True)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## Test Case 3: Multiple subplots with custom layout""")
    return


@app.cell
def _(df):
    # Test with 2x2 layout - also returns ndarray of Axes
    df[["distance", "total", "fare", "tip"]].plot.box(
        subplots=True, layout=(2, 2), figsize=(10, 8)
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    ## Test Case 4: 1D array of subplots

    Test with a single row of subplots.
    """
    )
    return


@app.cell
def _(df):
    # Returns 1D ndarray of Axes
    df[["fare", "tip", "tolls"]].plot.box(subplots=True, layout=(1, 3))
    return


if __name__ == "__main__":
    app.run()
