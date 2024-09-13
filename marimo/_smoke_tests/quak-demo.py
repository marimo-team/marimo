# Copyright 2024 Marimo. All rights reserved.
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars==1.5.0",
#     "quak==0.1.8",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.8.2"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import polars as pl
    import quak
    from vega_datasets import data
    return data, mo, pl, quak


@app.cell
def __(data):
    df = data.cars()
    return df,


@app.cell
def __(df, mo, quak):
    qwidget = quak.Widget(df)
    w = mo.ui.anywidget(qwidget)
    w
    return qwidget, w


@app.cell
def __():
    # w.value
    return


if __name__ == "__main__":
    app.run()
