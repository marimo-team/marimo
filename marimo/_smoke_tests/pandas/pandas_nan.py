# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "numpy",
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import numpy as np

    # This shouldn't print a runtime warning
    df = pd.DataFrame({"a": [1, 2, 3], "b": [np.nan, np.nan, np.nan]})
    df
    return mo, np, pd


@app.cell
def _(mo, np, pd):
    i = np.random.randint(10000)
    size = 12
    # Prints a runtime warning, but still displays correctly
    nan_df = pd.DataFrame({"id": [i] * size, "all_nan_col": [np.nan] * size})
    mo.ui.table(nan_df)
    return


if __name__ == "__main__":
    app.run()
