# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def __(data):
    cars = data.cars()
    return cars,


@app.cell
def __(cars, mo):
    # Default cars (406)
    default = mo.ui.table(cars)
    default
    return default,


@app.cell
def __(default):
    default._value_frontend
    return


@app.cell
def __(cars, mo):
    # JSON
    mo.ui.table(cars.to_dict(orient="records"))
    return


@app.cell
def __(cars, mo):
    # No pagination
    mo.ui.table(cars[0:20], pagination=False)
    return


@app.cell
def __(cars, mo):
    # Trimmed, no pagination
    mo.ui.table(cars[0:9])
    return


@app.cell
def __(cars, mo):
    # 21k cars, above DEFAULT_SUMMARY_CHARTS_ROW_LIMIT
    _more_cars = cars.sample(n=21_000, replace=True)
    more_cars = mo.ui.table(_more_cars)
    more_cars
    return more_cars,


@app.cell
def __(more_cars):
    more_cars.value
    return


@app.cell
def __(cars):
    # 1m cars, above DEFAULT_SUMMARY_STATS_ROW_LIMIT
    one_mil_cars = cars.sample(1_000_000 + 1, replace=True)
    # mo.ui.table(one_mil_cars)
    return one_mil_cars,


@app.cell
def __(cars, mo):
    mo.ui.dataframe(cars)
    return


if __name__ == "__main__":
    app.run()
