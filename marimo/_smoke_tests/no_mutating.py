# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
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


@app.cell
def _(text):
    text.value = ""


@app.cell
def _(text):
    text.on_change = ""


if __name__ == "__main__":
    app.run()
