# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.75"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def __(data, mo):
    options = data.list_datasets()
    dataset_dropdown = mo.ui.dropdown(options, label="Datasets", value="cars")
    dataset_dropdown
    return dataset_dropdown, options


@app.cell
def __(data, dataset_dropdown, mo):
    mo.stop(not dataset_dropdown.value)
    selected_dataset = dataset_dropdown.value
    df = data.__call__(selected_dataset)
    return df, selected_dataset


@app.cell
def __(df, mo):
    mo.ui.data_voyager(df)
    return


if __name__ == "__main__":
    app.run()
