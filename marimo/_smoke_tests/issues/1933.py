# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    from vega_datasets import data
    return (data,)


@app.cell
def _(data, mo):
    t = mo.ui.table(data.cars())
    return (t,)


@app.cell
def _(mo, t):
    dictionary = mo.ui.dictionary({
        "cars": t
    })
    id(dictionary["cars"]), dictionary
    return (dictionary,)


@app.cell
def _(dictionary):
    dictionary.value["cars"]
    return


if __name__ == "__main__":
    app.run()
