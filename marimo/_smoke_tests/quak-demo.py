# Copyright 2026 Marimo. All rights reserved.
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

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import quak
    from vega_datasets import data
    return data, mo, quak


@app.cell
def _(data):
    df = data.cars()
    return (df,)


@app.cell
def _(df, mo, quak):
    qwidget = quak.Widget(df)
    w = mo.ui.anywidget(qwidget)
    w
    return


@app.cell
def _():
    # w.value
    return


if __name__ == "__main__":
    app.run()
