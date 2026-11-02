# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def display_slider(mo):
    slider = mo.ui.slider(1, 10)
    mo.md(f"Here is a slider: {slider}")


@app.cell
def _(mo):
    element = mo.ui.checkbox(False)
    return (element,)


@app.cell
def display_element(element, mo):
    mo.md(f"Here is an element: {element}")


if __name__ == "__main__":
    app.run()
