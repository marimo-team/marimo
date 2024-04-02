# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.8"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def display_slider(mo):
    slider = mo.ui.slider(1, 10)
    mo.md(f"Here is a slider: {slider}")
    return slider,


@app.cell
def __(mo):
    element = mo.ui.checkbox(False)
    return element,


@app.cell
def display_element(element, mo):
    mo.md(f"Here is an element: {element}")
    return


if __name__ == "__main__":
    app.run()
