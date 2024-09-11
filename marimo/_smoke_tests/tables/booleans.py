# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas",
#     "polars",
# ]
# ///

import marimo

__generated_with = "0.8.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import polars as pl
    return mo, pd, pl


@app.cell
def __(pd):
    data = {
        "A": [True, True, True],
        "B": [False, False, False],
        "C": [True, True, False],
    }

    pd.DataFrame(data)
    return data,


@app.cell
def __(data, pl):
    pl.DataFrame(data)
    return


@app.cell
def __(data, mo):
    mo.ui.table(data)
    return


if __name__ == "__main__":
    app.run()
