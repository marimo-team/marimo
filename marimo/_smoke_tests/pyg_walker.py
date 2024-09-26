# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "pygwalker",
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import pandas as pd
    import pygwalker as pyg

    import marimo as mo
    return mo, pd, pyg


@app.cell
def __(pd):
    df = pd.read_csv(
        "https://raw.githubusercontent.com/plotly/datasets/master/gapminderDataFiveYear.csv"
    )
    return df,


@app.cell
def __(df, mo, pyg):
    walker = pyg.walk(df, kernel_computation=True)
    mo.Html(walker.to_html())
    return walker,


if __name__ == "__main__":
    app.run()
