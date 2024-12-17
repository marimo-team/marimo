
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "numpy==2.1.3",
#     "pandas==2.2.3",
# ]
# ///

import marimo

__generated_with = "0.9.27"
app = marimo.App(width="medium")


@app.cell
def __():
    import pandas as pd
    import marimo as mo
    import numpy as np
    return mo, np, pd


@app.cell
def __(mo):
    mo.md(r"""## Lots of columns""")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""Set cols to 10000 to crash the frontend. Number of rows appears to have no effect.""")
    return


@app.cell
def __(mo):
    rows = mo.ui.number(start=1, value=10, label="rows")
    columns = mo.ui.number(start=1, value=50, label="cols")

    mo.hstack([rows, columns], justify="start")
    return columns, rows


@app.cell
def __(columns, np, rows):
    data = np.zeros((rows.value, columns.value))
    return (data,)


@app.cell
def __(data, pd):
    df = pd.DataFrame(data, columns=[str(i) for i in range(1, data.shape[1] + 1)])
    return (df,)


@app.cell
def __(df):
    df
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        ## 20k rows, 40 columns 

        This is the default max to show column summaries
        """
    )
    return


@app.cell
def __(np, pd):
    _data = np.random.rand(20000, 40)
    column_names = [f"col{i}" for i in range(40)]
    large_df = pd.DataFrame(
        {col: _data[:, i] for i, col in enumerate(column_names)}
    )
    large_df
    return column_names, large_df


@app.cell
def __():
    # mo.ui.table(df, max_columns=None)
    return


if __name__ == "__main__":
    app.run()
