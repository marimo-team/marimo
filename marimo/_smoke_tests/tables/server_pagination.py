# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "vega-datasets",
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def _(data):
    cars = data.cars()
    return (cars,)


@app.cell
def _(cars, mo):
    # Default cars (406)
    default = mo.ui.table(cars)
    default
    return (default,)


@app.cell
def _(default):
    default._value_frontend
    return


@app.cell
def _(cars, mo):
    # JSON
    mo.ui.table(cars.to_dict(orient="records"))
    return


@app.cell
def _(cars, mo):
    # No pagination
    mo.ui.table(cars[0:20], pagination=False)
    return


@app.cell
def _(cars, mo):
    # Trimmed, no pagination
    mo.ui.table(cars[0:9])
    return


@app.cell
def _(cars, mo):
    # 21k cars, above DEFAULT_SUMMARY_CHARTS_ROW_LIMIT
    _more_cars = cars.sample(n=21_000, replace=True)
    more_cars = mo.ui.table(_more_cars)
    more_cars
    return (more_cars,)


@app.cell
def _(more_cars):
    more_cars.value
    return


@app.cell
def _(cars):
    # 1m cars, above DEFAULT_SUMMARY_STATS_ROW_LIMIT
    one_mil_cars = cars.sample(1_000_000 + 1, replace=True)
    # mo.ui.table(one_mil_cars)
    return


@app.cell
def _(cars, mo):
    mo.ui.dataframe(cars)
    return


if __name__ == "__main__":
    app.run()
