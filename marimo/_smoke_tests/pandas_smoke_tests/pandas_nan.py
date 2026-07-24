# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "numpy",
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import numpy as np

    return mo, np, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## All-NaN columns

    Related: [#7046](https://github.com/marimo-team/marimo/issues/7046) (Python
    `RuntimeWarning`), [#10303](https://github.com/marimo-team/marimo/issues/10303)
    (Vega console warnings from column summary charts).

    Column summary **charts** only render when the table has at least 11 rows
    (`DEFAULT_SUMMARY_CHARTS_MINIMUM_ROWS`). Below that, only stats show.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Below chart threshold (< 11 rows)

    Should display without a Python `RuntimeWarning` and without column charts.
    """)
    return


@app.cell
def _(np, pd):
    # This shouldn't print a runtime warning
    small_nan_df = pd.DataFrame(
        {"a": [1, 2, 3], "b": [np.nan, np.nan, np.nan]}
    )
    small_nan_df
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### At / above chart threshold (≥ 11 rows) — #7046

    Open the browser console. There should be no Python `RuntimeWarning`
    (`Mean of empty slice`) in the terminal, and no Vega
    `Infinite extent` / `Dropping ... aggregate max` warnings in the console.
    """)
    return


@app.cell
def _(mo, np, pd):
    i = np.random.randint(10000)
    size = 12
    nan_df = pd.DataFrame({"id": [i] * size, "all_nan_col": [np.nan] * size})
    mo.ui.table(nan_df)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Mixed columns with all-NaN — #10303

    Repro from the issue. With `N >= 6` (12+ rows), column summary charts
    appear. Column `b` is all-NaN; check the browser console for Vega warnings.
    """)
    return


@app.cell
def _(mo):
    n = mo.ui.slider(1, 20, value=6, label="N (rows = 2N)")
    n
    return (n,)


@app.cell
def _(mo, n, np, pd):
    N = n.value
    issue_df = pd.DataFrame(
        {
            "a": list("xy") * N,
            "b": [np.nan, np.nan] * N,
            "c": ([1, None] * N),
        }
    )
    mo.vstack(
        [
            mo.md(f"`{len(issue_df)}` rows — charts enabled: **{len(issue_df) >= 11}**"),
            mo.ui.table(issue_df),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
