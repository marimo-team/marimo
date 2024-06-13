# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.17"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    text = mo.ui.text(on_change=print)
    return text,


@app.cell
def __(text):
    text.on_change
    return


@app.cell
def __(text):
    text.value = ""
    return


@app.cell
def __(text):
    text.on_change = ""
    return


if __name__ == "__main__":
    app.run()
