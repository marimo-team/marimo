# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.12"
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
