# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pandas",
#     "openpyxl",
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
    mo.md("""# Issue #6898: DatetimeIndex Lost Across Cells""")
    return


@app.cell
def _():
    import pandas as pd
    import io

    # Load COVID-19 time series data from Johns Hopkins GitHub
    # This dataset has dates as columns, perfect for testing DatetimeIndex columns
    url = (
        "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/"
        "csse_covid_19_data/csse_covid_19_time_series/"
        "time_series_covid19_confirmed_US.csv"
    )

    # Read and prepare the data
    df_raw = pd.read_csv(url)

    # Get only the date columns (skip first 11 metadata columns)
    date_cols = df_raw.columns[11:]

    # Create a small subset for testing
    df_subset = df_raw.iloc[:5, 11:20].copy()
    df_subset
    return df_subset, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    ## Test Case 1: DataFrame with DatetimeIndex columns using pipe()

    This reproduces the exact issue from #6898 where `.pipe()` is used
    to set DatetimeIndex on columns.
    """
    )
    return


@app.cell
def _(df_subset, pd):
    # Reproduce the exact pattern from issue #6898
    df_with_datetime_cols = df_subset.pipe(
        lambda d: d.set_axis(pd.DatetimeIndex(pd.to_datetime(d.columns)), axis=1)
    )

    # In this cell, everything should work correctly
    print(f"Type in same cell: {type(df_with_datetime_cols.columns)}")
    print(f"Dtype in same cell: {df_with_datetime_cols.columns.dtype}")
    print(
        f"Is DatetimeIndex in same cell: {isinstance(df_with_datetime_cols.columns, pd.DatetimeIndex)}"
    )

    df_with_datetime_cols
    return (df_with_datetime_cols,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
    ## Test Case 2: Check column type in NEXT cell (reproduces bug)

    This is where the bug manifests - the DatetimeIndex is lost when
    the DataFrame is passed to the next cell.
    """
    )
    return


@app.cell
def _(df_with_datetime_cols, pd):
    # This should show DatetimeIndex
    print(f"Type in next cell: {type(df_with_datetime_cols.columns)}")
    print(f"Dtype in next cell: {df_with_datetime_cols.columns.dtype}")
    print(
        f"Is DatetimeIndex in next cell: {isinstance(df_with_datetime_cols.columns, pd.DatetimeIndex)}"
    )
    return


if __name__ == "__main__":
    app.run()
