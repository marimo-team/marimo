# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    from vega_datasets import data
    return data,


@app.cell
def __(data, mo):
    t = mo.ui.table(data.cars())
    return t,


@app.cell
def __(mo, t):
    dictionary = mo.ui.dictionary({
        "cars": t
    })
    id(dictionary["cars"]), dictionary
    return dictionary,


@app.cell
def __(dictionary):
    dictionary.value["cars"]
    return


if __name__ == "__main__":
    app.run()
