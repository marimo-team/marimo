# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    return mo, pd


@app.cell
def _(pd):
    all_flights = pd.read_parquet(
    "https://vegafusion-datasets.s3.amazonaws.com/vega/flights_1m.parquet"
    )
    return (all_flights,)


@app.cell
def _(all_flights, mo):
    mo.ui.table(all_flights)


@app.cell
def _(all_flights, mo):
    mo.ui.table(all_flights[0:10])


if __name__ == "__main__":
    app.run()
