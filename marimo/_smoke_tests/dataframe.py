# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.31"
app = marimo.App(width="full")


@app.cell
def __(cars, mo):
    dataframe = mo.ui.dataframe(cars)
    dataframe
    return dataframe,


@app.cell
def __(dataframe, mo):
    mo.ui.table(dataframe.value, selection=None)
    return


@app.cell
def __(dataframe):
    dataframe.value
    return


@app.cell
def __(dataframe):
    dataframe.value["Cylinders"]
    return


@app.cell
def __(dataframe, mo):
    mo.hstack([dataframe.value.to_dict("records"), dataframe.value.to_dict()])
    return


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import pandas as pd
    import vega_datasets

    cars = vega_datasets.data.cars()
    return cars, pd, vega_datasets


if __name__ == "__main__":
    app.run()
