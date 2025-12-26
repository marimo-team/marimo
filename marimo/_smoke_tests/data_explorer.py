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
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def _(data, mo):
    options = data.list_datasets()
    dataset_dropdown = mo.ui.dropdown(options, label="Datasets", value="cars")
    dataset_dropdown
    return (dataset_dropdown,)


@app.cell
def _(data, dataset_dropdown, mo):
    mo.stop(not dataset_dropdown.value)
    selected_dataset = dataset_dropdown.value
    df = data.__call__(selected_dataset)
    return (df,)


@app.cell
def _(df, mo):
    v = mo.ui.data_explorer(df)
    v
    return (v,)


@app.cell
def _(v):
    v.value
    return


if __name__ == "__main__":
    app.run()
