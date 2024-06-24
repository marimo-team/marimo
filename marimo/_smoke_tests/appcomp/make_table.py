# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.22"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    t = mo.ui.table({"a": [1, 2, 3], "b": [4, 5, 6]})
    return t,


@app.cell
def __(t):
    t
    return


if __name__ == "__main__":
    app.run()
