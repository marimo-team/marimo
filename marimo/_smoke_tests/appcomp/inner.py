# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.6.26"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md("# Innermost")
    return


@app.cell
def __(mo):
    x = mo.ui.number(1, 10)
    return x,


@app.cell
def __(x):
    x
    return


@app.cell
def __(mo):
    y = mo.ui.number(1, 10)
    return y,


@app.cell
def __(y):
    y
    return


@app.cell
def __(x, y):
    x.value + y.value
    return


if __name__ == "__main__":
    app.run()
