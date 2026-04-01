# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def display_slider(mo):
    """Display a slider UI element."""
    slider = mo.ui.slider(1, 10)
    mo.md(f"Here is a slider: {slider}")
    return


@app.cell
def _(mo):
    element = mo.ui.checkbox(False)
    return (element,)


@app.cell
def display_element(element, mo):
    """Display a checkbox UI element."""
    mo.md(f"Here is an element: {element}")
    return


if __name__ == "__main__":
    app.run()
