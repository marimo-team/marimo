# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    dict1={"hello": mo.ui.text(label="world")}
    dict2=mo.ui.dictionary({k: v.form() for k, v in dict1.items()})
    dict2
    return (dict2,)


@app.cell
def _(dict2):
    dict2.value
    return


if __name__ == "__main__":
    app.run()
