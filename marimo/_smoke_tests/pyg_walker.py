# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "pygwalker",
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import pygwalker as pyg

    import marimo as mo
    return mo, pd, pyg


@app.cell
def _(pd):
    df = pd.read_csv(
        "https://raw.githubusercontent.com/plotly/datasets/master/gapminderDataFiveYear.csv"
    )
    return (df,)


@app.cell
def _(df, mo, pyg):
    walker = pyg.walk(df, kernel_computation=True)
    mo.Html(walker.to_html())
    return


if __name__ == "__main__":
    app.run()
