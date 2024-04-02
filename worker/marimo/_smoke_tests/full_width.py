# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.22"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    checkbox = mo.ui.checkbox(label="Full width")
    checkbox.callout()
    return checkbox,


@app.cell
def __(checkbox, mo):
    mo.ui.text(label="Text", full_width=checkbox.value)
    return


@app.cell
def __(checkbox, mo):
    mo.ui.text_area(label="Text area", full_width=checkbox.value)
    return


@app.cell
def __(checkbox, mo):
    mo.ui.number(0, 10, label="Number", full_width=checkbox.value)
    return


@app.cell
def __(checkbox, mo):
    mo.ui.dropdown(label="Dropdown", options=["A", "B", "C"], full_width=checkbox.value)
    return


@app.cell
def __(checkbox, mo):
    mo.ui.multiselect(label="Multiselect", options=["A", "B", "C"], full_width=checkbox.value)
    return


@app.cell
def __(checkbox, mo):
    mo.ui.date(label="Date", full_width=checkbox.value)
    return


@app.cell
def __(checkbox, mo):
    mo.ui.button(label="Button", full_width=checkbox.value)
    return


@app.cell
def __(checkbox, mo):
    # Is this the behavior we want?
    mo.hstack([
        mo.ui.text(label="Input A", full_width=checkbox.value),
        mo.ui.text(label="Input B", full_width=checkbox.value)
    ])
    return


@app.cell
def __(checkbox, mo):
    mo.vstack([
        mo.ui.text(label="Input A", full_width=checkbox.value),
        mo.ui.text(label="Input B", full_width=checkbox.value)
    ])
    return


if __name__ == "__main__":
    app.run()
