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
    text = mo.ui.text(on_change=print)
    return (text,)


@app.cell
def _(text):
    text.on_change
    return


@app.cell
def _(text):
    text.value = ""
    return


@app.cell
def _(text):
    text.on_change = ""
    return


if __name__ == "__main__":
    app.run()
